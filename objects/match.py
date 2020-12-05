# -*- coding: utf-8 -*-

import asyncio
from datetime import datetime as dt, timedelta as td

from typing import Optional, Sequence, Union, TYPE_CHECKING
from dataclasses import dataclass
from collections import defaultdict
from enum import IntEnum, unique

from constants import regexes
from constants.mods import Mods
from constants.gamemodes import GameMode

from objects import glob
from objects.beatmap import Beatmap

import packets

if TYPE_CHECKING:
    from objects.player import Player
    from objects.channel import Channel

__all__ = (
    'SlotStatus',
    'Teams',
    'MatchTypes',
    'MatchScoringTypes',
    'MatchTeamTypes',
    'ScoreFrame',
    'MapPool',
    'Slot',
    'Match'
)

@unique
class SlotStatus(IntEnum):
    open       = 1
    locked     = 2
    not_ready  = 4
    ready      = 8
    no_map     = 16
    playing    = 32
    complete   = 64
    quit       = 128

    has_player = not_ready | ready | no_map | playing | complete

@unique
class Teams(IntEnum):
    neutral = 0
    blue    = 1
    red     = 2

@unique
class MatchTypes(IntEnum):
    standard  = 0
    powerplay = 1 # literally no idea what this is for

@unique
class MatchScoringTypes(IntEnum):
    score    = 0
    accuracy = 1
    combo    = 2
    scorev2  = 3

@unique
class MatchTeamTypes(IntEnum):
    head_to_head = 0
    tag_coop     = 1
    team_vs      = 2
    tag_team_vs  = 3

@dataclass
class ScoreFrame:
    time: int
    id: int
    num300: int
    num100: int
    num50: int
    num_geki: int
    num_katu: int
    num_miss: int
    total_score: int
    current_combo: int
    max_combo: int
    perfect: bool
    current_hp: int
    tag_byte: int

    score_v2: bool
    # scorev2 only
    combo_portion: Optional[float] = None
    bonus_portion: Optional[float] = None

class MapPool:
    __slots__ = ('id', 'name', 'created_at', 'created_by', 'maps')
    def __init__(self, id: int, name: str,
                 created_at: dt, created_by: 'Player') -> None:
        self.id = id
        self.name = name
        self.created_at = created_at
        self.created_by = created_by

        self.maps = {} # {(mods: Mods, slot: int): Beatmap(), ...}

    def __repr__(self) -> str:
        return f'<{self.name}>'

    async def maps_from_sql(self) -> None:
        """Retrieve all maps from sql to populate `self.maps`."""
        query = ('SELECT map_id, mods, slot '
                 'FROM tourney_pool_maps '
                 'WHERE pool_id = %s')

        async for row in glob.db.iterall(query, [self.id]):
            key = (Mods(row['mods']), row['slot'])
            bmap = await Beatmap.from_bid(row['map_id'])

            # TODO: should prolly delete the map from pool and
            # inform eventually webhook to disc if not found?
            self.maps[key] = bmap

class Slot:
    """A class to represent a single slot in an osu! multiplayer match."""
    __slots__ = ('player', 'status', 'team',
                 'mods', 'loaded', 'skipped')

    def __init__(self) -> None:
        self.player: Optional['Player'] = None
        self.status = SlotStatus.open
        self.team = Teams.neutral
        self.mods = Mods.NOMOD
        self.loaded = False
        self.skipped = False

    def empty(self) -> bool:
        return self.player is None

    def copy(self, s) -> None:
        self.player = s.player
        self.status = s.status
        self.team = s.team
        self.mods = s.mods

    def reset(self) -> None:
        self.player = None
        self.status = SlotStatus.open
        self.team = Teams.neutral
        self.mods = Mods.NOMOD
        self.loaded = False
        self.skipped = False

class Match:
    """\
    A class to represent an osu! multiplayer match.

    Possibly confusing attributes
    -----------
    _refs: set[`Player`]
        A set of players who have access to mp commands in the match.
        These can be used with the !mp <addref/rmref/listref> commands.

    slots: list[`Slot`]
        A list of 16 `Slot` objects representing the match's slots.

    type: `MatchTypes`
        I have no idea why this exists.

    seed: `int`
        The seed used for osu!mania's random mod.

    """
    __slots__ = (
        'id', 'name', 'passwd', 'host', '_refs',
        'map_id', 'map_md5', 'map_name',
        'mods', 'freemods', 'mode',
        'chat', 'slots',
        'type', 'team_type', 'win_condition',
        'in_progress', 'seed',

        # tourney stuff
        'pool', 'match_points', 'bans', 'best_of'
    )

    def __init__(self) -> None:
        self.id = 0
        self.name = ''
        self.passwd = ''

        self.host = None
        self._refs = set()

        self.map_id = 0
        self.map_md5 = ''
        self.map_name = ''

        self.mods = Mods.NOMOD
        self.mode = GameMode.vn_std
        self.freemods = False

        self.chat: Optional['Channel'] = None #multiplayer
        self.slots = [Slot() for _ in range(16)]

        self.type = MatchTypes.standard
        self.team_type = MatchTeamTypes.head_to_head
        self.win_condition = MatchScoringTypes.score

        self.in_progress = False
        self.seed = 0

        # tourney stuff
        self.pool: Optional[MapPool] = None
        self.match_points = defaultdict(int) # {team/user: wins, ...} (resets when changing teams)
        self.bans = set() # {(mods, slot), ...}
        self.best_of = 0

    @property
    def url(self) -> str:
        """The match's invitation url."""
        return f'osump://{self.id}/{self.passwd}'

    @property
    def map_url(self):
        """The osu! beatmap url for `self`'s map."""
        return f'https://osu.ppy.sh/b/{self.map_id}'

    @property
    def embed(self) -> str:
        """An osu! chat embed for `self`."""
        return f'[{self.url} {self.name}]'

    @property
    def map_embed(self) -> str:
        """An osu! chat embed for `self`'s map."""
        return f'[{self.map_url} {self.map_name}]'

    @property
    def refs(self) -> set['Player']:
        """Return all players with referee permissions."""
        return {self.host} | self._refs

    def __contains__(self, p: 'Player') -> bool:
        return p in {s.player for s in self.slots}

    def __getitem__(self, key: Union[int, slice]) -> Slot:
        return self.slots[key]

    def __repr__(self) -> str:
        return f'<{self.name} ({self.id})>'

    def get_slot(self, p: 'Player') -> Optional[Slot]:
        # get the slot containing a given player.
        for s in self.slots:
            if p is s.player:
                return s

    def get_slot_id(self, p: 'Player') -> Optional[int]:
        # get the slot index containing a given player.
        for idx, s in enumerate(self.slots):
            if p is s.player:
                return idx

    def get_free(self) -> Optional[Slot]:
        # get the first free slot index.
        for idx, s in enumerate(self.slots):
            if s.status == SlotStatus.open:
                return idx

    def get_host_slot(self) -> Optional[Slot]:
        for s in self.slots:
            if s.status & SlotStatus.has_player \
            and s.player is self.host:
                return s

        return

    def copy(self, m: 'Match') -> None:
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

    def enqueue(self, data: bytes, lobby: bool = True,
                immune: Sequence[int] = []) -> None:
        """Add data to be sent to all clients in the match."""
        if not self.chat:
            breakpoint()

        self.chat.enqueue(data, immune)

        if lobby and (lchan := glob.channels['#lobby']) and lchan.players:
            lchan.enqueue(data)

    def enqueue_state(self, lobby: bool = True) -> None:
        """Enqueue `self`'s state to players in the match & lobby."""
        if not self.chat:
            breakpoint()

        # TODO: hmm this is pretty bad, writes twice

        # send password only to users currently in the match.
        self.chat.enqueue(packets.updateMatch(self, send_pw=True))

        if lobby and (lchan := glob.channels['#lobby']) and lchan.players:
            lchan.enqueue(packets.updateMatch(self, send_pw=False))

    def unready_players(self, expected: SlotStatus = SlotStatus.ready) -> None:
        """Unready any players in the `expected` state."""
        for s in self.slots:
            if s.status == expected:
                s.status = SlotStatus.not_ready

    def start(self) -> None:
        no_map: list[Player] = []

        for s in self.slots:
            # start each player who has the map.
            if s.status & SlotStatus.has_player:
                if s.status != SlotStatus.no_map:
                    s.status = SlotStatus.playing
                else:
                    no_map.append(s.player.id)

        self.in_progress = True
        self.enqueue(packets.matchStart(self), immune=no_map)
        self.enqueue_state()

    # NOTE: i don't actually think this can determine ties atm? coming soon..
    async def update_matchpoints(self, was_playing: list['Player']) -> None:
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
          United States takes the match, finishing with a score of 7 - 2!

        FFA, the top <=3 players will be listed for the total score.
          Justice takes the point! (94.32% [Match avg. 91.22%])
          Total Score: Justice - 3 | cmyui - 2 | FrostiDrinks - 2
          Justice takes the match, finishing with a score of 4 - 2!
        """

        # this will return a dict of scores if it finds scores
        # from all players, otherwise it will return the player
        # it finds first that doesn't submit a score.
        # TODO: refactor the whole thing to make it individually
        # try to retrieve each players score separately in async,
        # so 1. its async, 2. it can return a list of players who
        # didn't submit a score instead.
        ret = await self.await_submissions(was_playing)

        if not isinstance(ret, dict):
            # Player failed to submit a score in time.
            await self.chat.send(glob.bot, f"{ret} didn't submit a score in time.")
            return

        await self._update_matchpoints(ret)

    async def await_submissions(self, was_playing: list['Player']) -> Optional[dict[str, Union[int, float]]]:
        """Await score submissions from all players in completed state."""
        scores = defaultdict(int)
        time_taken = 0 # allow up to 15s

        ffa = self.team_type in (MatchTeamTypes.head_to_head,
                                 MatchTeamTypes.tag_coop)
        win_cond = ('score', 'acc', 'max_combo', 'score')[self.win_condition]

        for s in was_playing:
            # continue trying to fetch each player's
            # scores until they've all been submitted.
            while True:
                rc_score = s.player.recent_score

                if rc_score and rc_score.bmap.md5 == self.map_md5 \
                and rc_score.play_time > dt.now() - td(seconds=15):
                    # score found, add to our scores dict if != 0.
                    if score := getattr(rc_score, win_cond):
                        key = s.player if ffa else s.team
                        scores[key] += score

                    break

                # wait 0.5s and try again
                await asyncio.sleep(0.5)
                time_taken += 0.5

                if time_taken > 15:
                    # inform the match this user didn't
                    # submit a score in time, and thus
                    # the score couldn't be autocalced.
                    return s.player

        # all scores retrieved, update the match.
        return scores

    async def _update_matchpoints(self, scores: dict[str, Union[int, float]]) -> None:
        ffa = self.team_type in (MatchTeamTypes.head_to_head,
                                 MatchTeamTypes.tag_coop)

        # Find the winner & increment their matchpoints.
        winner = max(scores, key=scores.get)
        self.match_points[winner] += 1

        msg: list[str] = []

        def add_suffix(score: Union[int, float]) -> Union[str, int, float]:
            if self.win_condition == MatchScoringTypes.accuracy:
                return f'{score:.2f}%'
            elif self.win_condition == MatchScoringTypes.combo:
                return f'{score}x'
            else:
                return str(score)

        if ffa:
            msg.append(
                f'{winner.name} takes the point! ({add_suffix(scores[winner])} '
                f'[Match avg. {add_suffix(int(sum(scores.values()) / len(scores)))}])'
            )

            wmp = self.match_points[winner]

            # check if match point #1 has enough points to win.
            if self.best_of and (wmp // 2) + 1 > self.best_of:
                # we have a champion, announce & reset our match.
                self.best_of = 0
                self.match_points.clear()
                self.bans.clear()

                msg.append(f'{winner.name} takes the match! Congratulations!')
            else:
                # no winner, just announce the match points so far.
                # for ffa, we'll only announce the top <=3 players.
                m_points = sorted(self.match_points.items(), key=lambda x: x[1])
                msg.append('Total Score: ' + ' | '.join(f'{k.name} - {v}' for k, v in m_points))

        else: # teams
            # TODO: check if the teams are named or not
            if rgx := regexes.tourney_matchname.match(self.name):
                match_name = rgx['name']
                team_names = {Teams.blue: rgx['T1'],
                              Teams.red: rgx['T2']}
            else:
                match_name = self.name
                team_names = {Teams.blue: 'Blue',
                              Teams.red: 'Red'}

            loser = Teams({1: 2, 2: 1}[winner])

            # w/l = winner/loser

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
            msg.append(f'{wname} takes the point! ({ws} vs. {ls})')

            # check if the winner has enough match points to win the match.
            if self.best_of and (wmp // 2) + 1 > self.best_of:
                # we have a champion, announce & reset our match.
                self.best_of = 0
                self.match_points.clear()
                self.bans.clear()

                msg.append(f'{wname} takes the match, finishing {match_name} with a score of {wmp} - {lmp}!')
            else:
                # no winner, just announce the match points so far.
                msg.append(f'Total Score: {wname} | {wmp} - {lmp} | {lname}')

        for line in msg:
            await self.chat.send(glob.bot, line)
