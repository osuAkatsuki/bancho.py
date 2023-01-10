from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime as datetime
from datetime import timedelta as timedelta
from enum import IntEnum
from enum import unique
from typing import Optional
from typing import overload
from typing import Sequence
from typing import TYPE_CHECKING
from typing import TypedDict
from typing import Union

import databases.core

import app.packets
import app.settings
import app.state
from app.constants import regexes
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.logging import Ansi
from app.logging import log
from app.objects.beatmap import Beatmap
from app.utils import escape_enum
from app.utils import pymysql_encode

if TYPE_CHECKING:
    from asyncio import TimerHandle

    from app.objects.player import Player
    from app.objects.channel import Channel

__all__ = (
    "SlotStatus",
    "MatchTeams",
    #'MatchTypes',
    "MatchWinConditions",
    "MatchTeamTypes",
    "MapPool",
    "Slot",
    "Match",
)


@unique
@pymysql_encode(escape_enum)
class SlotStatus(IntEnum):
    open = 1
    locked = 2
    not_ready = 4
    ready = 8
    no_map = 16
    playing = 32
    complete = 64
    quit = 128

    # has_player = not_ready | ready | no_map | playing | complete


@unique
@pymysql_encode(escape_enum)
class MatchTeams(IntEnum):
    neutral = 0
    blue = 1
    red = 2


"""
# implemented by osu! and send between client/server,
# quite frequently even, but seems useless??
@unique
@pymysql_encode(escape_enum)
class MatchTypes(IntEnum):
    standard  = 0
    powerplay = 1 # literally no idea what this is for
"""


@unique
@pymysql_encode(escape_enum)
class MatchWinConditions(IntEnum):
    score = 0
    accuracy = 1
    combo = 2
    scorev2 = 3


@unique
@pymysql_encode(escape_enum)
class MatchTeamTypes(IntEnum):
    head_to_head = 0
    tag_coop = 1
    team_vs = 2
    tag_team_vs = 3


class MapPool:
    def __init__(
        self,
        id: int,
        name: str,
        created_at: datetime,
        created_by: Player,
    ) -> None:
        self.id = id
        self.name = name
        self.created_at = created_at
        self.created_by = created_by

        self.maps: dict[
            tuple[Mods, int],
            Beatmap,
        ] = {}

    def __repr__(self) -> str:
        return f"<{self.name}>"

    async def maps_from_sql(self, db_conn: databases.core.Connection) -> None:
        """Retrieve all maps from sql to populate `self.maps`."""
        for row in await db_conn.fetch_all(
            "SELECT map_id, mods, slot FROM tourney_pool_maps WHERE pool_id = :pool_id",
            {"pool_id": self.id},
        ):
            map_id = row["map_id"]
            bmap = await Beatmap.from_bid(map_id)

            if not bmap:
                # map not found? remove it from the
                # pool and log this incident to console.
                # NOTE: it's intentional that this removes
                # it from not only this pool, but all pools.
                # TODO: perhaps discord webhook?
                log(f"Removing {map_id} from pool {self.name} (not found).", Ansi.LRED)

                await db_conn.execute(
                    "DELETE FROM tourney_pool_maps WHERE map_id = :map_id",
                    {"map_id": map_id},
                )
                continue

            key: tuple[Mods, int] = (Mods(row["mods"]), row["slot"])
            self.maps[key] = bmap


class Slot:
    """An individual player slot in an osu! multiplayer match."""

    def __init__(self) -> None:
        self.player: Optional[Player] = None
        self.status = SlotStatus.open
        self.team = MatchTeams.neutral
        self.mods = Mods.NOMOD
        self.loaded = False
        self.skipped = False

    def empty(self) -> bool:
        return self.player is None

    def copy_from(self, other: Slot) -> None:
        self.player = other.player
        self.status = other.status
        self.team = other.team
        self.mods = other.mods

    def reset(self, new_status: SlotStatus = SlotStatus.open) -> None:
        self.player = None
        self.status = new_status
        self.team = MatchTeams.neutral
        self.mods = Mods.NOMOD
        self.loaded = False
        self.skipped = False


class StartingTimers(TypedDict):
    start: TimerHandle
    alerts: list[TimerHandle]
    time: float


class Match:
    """\
    An osu! multiplayer match.

    Possibly confusing attributes
    -----------
    _refs: set[`Player`]
        A set of players who have access to mp commands in the match.
        These can be used with the !mp <addref/rmref/listref> commands.

    slots: list[`Slot`]
        A list of 16 `Slot` objects representing the match's slots.

    starting: Optional[dict[str, `TimerHandle`]]
        Used when the match is started with !mp start <seconds>.
        It stores both the starting timer, and the chat alert timers.

    seed: `int`
        The seed used for osu!mania's random mod.

    use_pp_scoring: `bool`
        Whether pp should be used as a win condition override during scrims.
    """

    def __init__(
        self,
        id: int,
        name: str,
        password: str,
        map_name: str,
        map_id: int,
        map_md5: str,
        host_id: int,
        mode: GameMode,
        mods: Mods,
        win_condition: MatchWinConditions,
        team_type: MatchTeamTypes,
        freemods: bool,
        seed: int,
        chat_channel: Channel,
    ) -> None:
        self.id = id
        self.name = name
        self.passwd = password

        self.host_id = host_id
        self._refs: set[Player] = set()

        self.map_id = map_id
        self.map_md5 = map_md5
        self.map_name = map_name
        self.prev_map_id = 0  # previously chosen map

        self.mods = mods
        self.mode = mode
        self.freemods = freemods

        self.chat = chat_channel
        self.slots = [Slot() for _ in range(16)]

        # self.type = MatchTypes.standard
        self.team_type = team_type
        self.win_condition = win_condition

        self.in_progress = False
        self.starting: Optional[StartingTimers] = None
        self.seed = seed  # used for mania random mod

        self.pool: Optional[MapPool] = None

        # scrimmage stuff
        self.is_scrimming = False
        self.match_points: dict[Union[MatchTeams, Player], int] = defaultdict(int)
        self.bans: set[tuple[Mods, int]] = set()
        self.winners: list[Union[Player, MatchTeams, None]] = []  # none for tie
        self.winning_pts = 0
        self.use_pp_scoring = False  # only for scrims

        self.tourney_clients: set[int] = set()  # player ids

    @property  # TODO: test cache speed
    def host(self) -> Player:
        player = app.state.sessions.players.get(id=self.host_id)
        assert player is not None
        return player

    @property
    def url(self) -> str:
        """The match's invitation url."""
        return f"osump://{self.id}/{self.passwd}"

    @property
    def map_url(self):
        """The osu! beatmap url for `self`'s map."""
        return f"https://osu.{app.settings.DOMAIN}/beatmapsets/#/{self.map_id}"

    @property
    def embed(self) -> str:
        """An osu! chat embed for `self`."""
        return f"[{self.url} {self.name}]"

    @property
    def map_embed(self) -> str:
        """An osu! chat embed for `self`'s map."""
        return f"[{self.map_url} {self.map_name}]"

    @property
    def refs(self) -> set[Player]:
        """Return all players with referee permissions."""
        refs = self._refs

        if self.host is not None:
            refs.add(self.host)

        return refs

    def __repr__(self) -> str:
        return f"<{self.name} ({self.id})>"

    def get_slot(self, player: Player) -> Optional[Slot]:
        """Return the slot containing a given player."""
        for s in self.slots:
            if player is s.player:
                return s

        return None

    def get_slot_id(self, player: Player) -> Optional[int]:
        """Return the slot index containing a given player."""
        for idx, s in enumerate(self.slots):
            if player is s.player:
                return idx

        return None

    def get_free(self) -> Optional[int]:
        """Return the first unoccupied slot in multi, if any."""
        for idx, s in enumerate(self.slots):
            if s.status == SlotStatus.open:
                return idx

        return None

    def get_host_slot(self) -> Optional[Slot]:
        """Return the slot containing the host."""
        for s in self.slots:
            if s.player is not None and s.player is self.host:
                return s

        return None

    def copy(self, m: Match) -> None:
        """Fully copy the data of another match obj."""
        self.map_id = m.map_id
        self.map_md5 = m.map_md5
        self.map_name = m.map_name
        self.freemods = m.freemods
        self.mode = m.mode
        self.team_type = m.team_type
        self.win_condition = m.win_condition
        self.mods = m.mods
        self.name = m.name

    def enqueue(
        self,
        data: bytes,
        lobby: bool = True,
        immune: Sequence[int] = [],
    ) -> None:
        """Add data to be sent to all clients in the match."""
        self.chat.enqueue(data, immune)

        lchan = app.state.sessions.channels["#lobby"]
        if lobby and lchan and lchan.players:
            lchan.enqueue(data)

    def enqueue_state(self, lobby: bool = True) -> None:
        """Enqueue `self`'s state to players in the match & lobby."""
        # TODO: hmm this is pretty bad, writes twice

        # send password only to users currently in the match.
        self.chat.enqueue(app.packets.update_match(self, send_pw=True))

        lchan = app.state.sessions.channels["#lobby"]
        if lobby and lchan and lchan.players:
            lchan.enqueue(app.packets.update_match(self, send_pw=False))

    def unready_players(self, expected: SlotStatus = SlotStatus.ready) -> None:
        """Unready any players in the `expected` state."""
        for s in self.slots:
            if s.status == expected:
                s.status = SlotStatus.not_ready

    def start(self) -> None:
        """Start the match for all ready players with the map."""
        no_map: list[int] = []

        for s in self.slots:
            # start each player who has the map.
            if s.player is not None:
                if s.status != SlotStatus.no_map:
                    s.status = SlotStatus.playing
                else:
                    no_map.append(s.player.id)

        self.in_progress = True
        self.enqueue(app.packets.match_start(self), immune=no_map, lobby=False)
        self.enqueue_state()

    def reset_scrim(self) -> None:
        """Reset the current scrim's winning points & bans."""
        self.match_points.clear()
        self.winners.clear()
        self.bans.clear()

    async def await_submissions(
        self,
        was_playing: Sequence[Slot],
    ) -> tuple[dict[Union[MatchTeams, Player], int], Sequence[Player]]:
        """Await score submissions from all players in completed state."""
        scores: dict[Union[MatchTeams, Player], int] = defaultdict(int)
        didnt_submit: list[Player] = []
        time_waited = 0  # allow up to 10s (total, not per player)

        ffa = self.team_type in (MatchTeamTypes.head_to_head, MatchTeamTypes.tag_coop)

        if self.use_pp_scoring:
            win_cond = "pp"
        else:
            win_cond = ("score", "acc", "max_combo", "score")[self.win_condition]

        bmap = await Beatmap.from_md5(self.map_md5)

        if not bmap:
            # map isn't submitted
            return {}, ()

        for s in was_playing:
            # continue trying to fetch each player's
            # scores until they've all been submitted.
            while True:
                rc_score = s.player.recent_score
                max_age = datetime.now() - timedelta(
                    seconds=bmap.total_length + time_waited + 0.5,
                )

                if (
                    rc_score
                    and rc_score.bmap.md5 == self.map_md5
                    and rc_score.server_time > max_age
                ):
                    # score found, add to our scores dict if != 0.
                    score = getattr(rc_score, win_cond)
                    if score:
                        key = s.player if ffa else s.team
                        scores[key] += score

                    break

                # wait 0.5s and try again
                await asyncio.sleep(0.5)
                time_waited += 0.5

                if time_waited > 10:
                    # inform the match this user didn't
                    # submit a score in time, and skip them.
                    didnt_submit.append(s.player)
                    break

        # all scores retrieved, update the match.
        return scores, didnt_submit

    async def update_matchpoints(self, was_playing: Sequence[Slot]) -> None:
        """\
        Determine the winner from `scores`, increment & inform players.

        This automatically works with the match settings (such as
        win condition, teams, & co-op) to determine the appropriate
        winner, and will use any team names included in the match name,
        along with the match name (fmt: OWC2020: (Team1) vs. (Team2)).

        For the examples, we'll use accuracy as a win condition.

        Teams, match title: `OWC2015: (United States) vs. (China)`.
          United States takes the point! (293.32% vs 292.12%)
          Total Score: United States | 7 - 2 | China
          United States takes the match, finishing OWC2015 with a score of 7 - 2!

        FFA, the top <=3 players will be listed for the total score.
          Justice takes the point! (94.32% [Match avg. 91.22%])
          Total Score: Justice - 3 | cmyui - 2 | FrostiDrinks - 2
          Justice takes the match, finishing with a score of 4 - 2!
        """

        scores, didnt_submit = await self.await_submissions(was_playing)

        for player in didnt_submit:
            self.chat.send_bot(f"{player} didn't submit a score (timeout: 10s).")

        if scores:
            ffa = self.team_type in (
                MatchTeamTypes.head_to_head,
                MatchTeamTypes.tag_coop,
            )

            # all scores are equal, it was a tie.
            if len(scores) != 1 and len(set(scores.values())) == 1:
                self.winners.append(None)
                self.chat.send_bot("The point has ended in a tie!")
                return None

            # Find the winner & increment their matchpoints.
            winner: Union[Player, MatchTeams] = max(scores, key=lambda k: scores[k])
            self.winners.append(winner)
            self.match_points[winner] += 1

            msg: list[str] = []

            def add_suffix(score: int | float) -> str | int | float:
                if self.use_pp_scoring:
                    return f"{score:.2f}pp"
                elif self.win_condition == MatchWinConditions.accuracy:
                    return f"{score:.2f}%"
                elif self.win_condition == MatchWinConditions.combo:
                    return f"{score}x"
                else:
                    return str(score)

            if ffa:
                msg.append(
                    f"{winner.name} takes the point! ({add_suffix(scores[winner])} "
                    f"[Match avg. {add_suffix(sum(scores.values()) / len(scores))}])",
                )

                wmp = self.match_points[winner]

                # check if match point #1 has enough points to win.
                if self.winning_pts and wmp == self.winning_pts:
                    # we have a champion, announce & reset our match.
                    self.is_scrimming = False
                    self.reset_scrim()
                    self.bans.clear()

                    m = f"{winner.name} takes the match! Congratulations!"
                else:
                    # no winner, just announce the match points so far.
                    # for ffa, we'll only announce the top <=3 players.
                    m_points = sorted(self.match_points.items(), key=lambda x: x[1])
                    m = f"Total Score: {' | '.join([f'{k.name} - {v}' for k, v in m_points])}"

                msg.append(m)
                del m

            else:  # teams
                r_match = regexes.TOURNEY_MATCHNAME.match(self.name)
                if r_match:
                    match_name = r_match["name"]
                    team_names = {
                        MatchTeams.blue: r_match["T1"],
                        MatchTeams.red: r_match["T2"],
                    }
                else:
                    match_name = self.name
                    team_names = {MatchTeams.blue: "Blue", MatchTeams.red: "Red"}

                # teams are binary, so we have a loser.
                loser = MatchTeams({1: 2, 2: 1}[winner])

                # from match name if available, else blue/red.
                wname = team_names[winner]
                lname = team_names[loser]

                # scores from the recent play
                # (according to win condition)
                ws = add_suffix(scores[winner])
                ls = add_suffix(scores[loser])

                # total win/loss score in the match.
                wmp = self.match_points[winner]
                lmp = self.match_points[loser]

                # announce the score for the most recent play.
                msg.append(f"{wname} takes the point! ({ws} vs. {ls})")

                # check if the winner has enough match points to win the match.
                if self.winning_pts and wmp == self.winning_pts:
                    # we have a champion, announce & reset our match.
                    self.is_scrimming = False
                    self.reset_scrim()

                    msg.append(
                        f"{wname} takes the match, finishing {match_name} "
                        f"with a score of {wmp} - {lmp}! Congratulations!",
                    )
                else:
                    # no winner, just announce the match points so far.
                    msg.append(f"Total Score: {wname} | {wmp} - {lmp} | {lname}")

            if didnt_submit:
                self.chat.send_bot(
                    "If you'd like to perform a rematch, "
                    "please use the `!mp rematch` command.",
                )

            for line in msg:
                self.chat.send_bot(line)

        else:
            self.chat.send_bot("Scores could not be calculated.")
