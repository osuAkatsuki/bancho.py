from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import date
from enum import Enum
from enum import IntEnum
from enum import unique
from functools import cached_property
from typing import Any
from typing import Optional
from typing import TYPE_CHECKING
from typing import TypedDict
from typing import Union

import databases.core

import app.packets
import app.settings
import app.state
from app._typing import IPAddress
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.constants.privileges import ClientPrivileges
from app.constants.privileges import Privileges
from app.discord import Webhook
from app.logging import Ansi
from app.logging import log
from app.objects.channel import Channel
from app.objects.match import Match
from app.objects.match import MatchTeams
from app.objects.match import MatchTeamTypes
from app.objects.match import Slot
from app.objects.match import SlotStatus
from app.objects.menu import Menu
from app.objects.menu import menu_keygen
from app.objects.menu import MenuCommands
from app.objects.menu import MenuFunction
from app.objects.score import Grade
from app.objects.score import Score
from app.utils import escape_enum
from app.utils import make_safe_name
from app.utils import pymysql_encode

if TYPE_CHECKING:
    from app.objects.achievement import Achievement
    from app.objects.beatmap import Beatmap
    from app.objects.clan import Clan
    from app.constants.privileges import ClanPrivileges

__all__ = ("ModeData", "Status", "Player")


@unique
@pymysql_encode(escape_enum)
class PresenceFilter(IntEnum):
    """osu! client side filter for which users the player can see."""

    Nil = 0
    All = 1
    Friends = 2


@unique
@pymysql_encode(escape_enum)
class Action(IntEnum):
    """The client's current app.state."""

    Idle = 0
    Afk = 1
    Playing = 2
    Editing = 3
    Modding = 4
    Multiplayer = 5
    Watching = 6
    Unknown = 7
    Testing = 8
    Submitting = 9
    Paused = 10
    Lobby = 11
    Multiplaying = 12
    OsuDirect = 13


@dataclass
class ModeData:
    """A player's stats in a single gamemode."""

    tscore: int
    rscore: int
    pp: int
    acc: float
    plays: int
    playtime: int
    max_combo: int
    total_hits: int
    rank: int  # global

    grades: dict[Grade, int]  # XH, X, SH, S, A


@dataclass
class Status:
    """The current status of a player."""

    action: Action = Action.Idle
    info_text: str = ""
    map_md5: str = ""
    mods: Mods = Mods.NOMOD
    mode: GameMode = GameMode.VANILLA_OSU
    map_id: int = 0


# temporary menu-related stuff
async def bot_hello(p: Player) -> None:
    p.send_bot(f"hello {p.name}!")


async def notif_hello(p: Player) -> None:
    p.enqueue(app.packets.notification(f"hello {p.name}!"))


MENU2 = Menu(
    "Second Menu",
    {
        menu_keygen(): (MenuCommands.Back, None),
        menu_keygen(): (MenuCommands.Execute, MenuFunction("notif_hello", notif_hello)),
    },
)

MAIN_MENU = Menu(
    "Main Menu",
    {
        menu_keygen(): (MenuCommands.Execute, MenuFunction("bot_hello", bot_hello)),
        menu_keygen(): (MenuCommands.Execute, MenuFunction("notif_hello", notif_hello)),
        menu_keygen(): (MenuCommands.Advance, MENU2),
    },
)


class LastNp(TypedDict):
    bmap: Beatmap
    mode_vn: int
    timeout: float


class OsuStream(str, Enum):
    STABLE = "stable"
    BETA = "beta"
    CUTTINGEDGE = "cuttingedge"
    TOURNEY = "tourney"
    DEV = "dev"


class OsuVersion:
    # b20200201.2cuttingedge
    # date = 2020/02/01
    # revision = 2
    # stream = cuttingedge
    def __init__(
        self,
        date: date,
        revision: Optional[int],  # TODO: should this be optional?
        stream: OsuStream,
    ) -> None:
        self.date = date
        self.revision = revision
        self.stream = stream


class ClientDetails:
    def __init__(
        self,
        osu_version: OsuVersion,
        osu_path_md5: str,
        adapters_md5: str,
        uninstall_md5: str,
        disk_signature_md5: str,
        adapters: list[str],
        ip: IPAddress,
    ) -> None:
        self.osu_version = osu_version
        self.osu_path_md5 = osu_path_md5
        self.adapters_md5 = adapters_md5
        self.uninstall_md5 = uninstall_md5
        self.disk_signature_md5 = disk_signature_md5

        self.adapters = adapters
        self.ip = ip

    @cached_property
    def client_hash(self) -> str:
        return (
            # NOTE the extra '.' and ':' appended to ends
            f"{self.osu_path_md5}:{'.'.join(self.adapters)}."
            f":{self.adapters_md5}:{self.uninstall_md5}:{self.disk_signature_md5}:"
        )

    # TODO: __str__ to pack like osu! hashes?


class Player:
    """\
    Server side representation of a player; not necessarily online.

    Possibly confusing attributes
    -----------
    token: `str`
        The player's unique token; used to
        communicate with the osu! client.

    safe_name: `str`
        The player's username (safe).
        XXX: Equivalent to `cls.name.lower().replace(' ', '_')`.

    pm_private: `bool`
        Whether the player is blocking pms from non-friends.

    silence_end: `int`
        The UNIX timestamp the player's silence will end at.

    pres_filter: `PresenceFilter`
        The scope of users the client can currently see.

    bot_client: `bool`
        Whether this is a bot account.

    tourney_client: `bool`
        Whether this is a management/spectator tourney client.

    _queue: `bytearray`
        Bytes enqueued to the player which will be transmitted
        at the tail end of their next connection to the server.
        XXX: cls.enqueue() will add data to this queue, and
             cls.dequeue() will return the data, and remove it.
    """

    def __init__(
        self,
        id: int,
        name: str,
        priv: Union[int, Privileges],
        **extras: Any,
    ) -> None:
        self.id = id
        self.name = name
        self.safe_name = self.make_safe(self.name)

        if "pw_bcrypt" in extras:
            self.pw_bcrypt: Optional[bytes] = extras["pw_bcrypt"]
        else:
            self.pw_bcrypt = None

        # generate a token if not given
        token = extras.get("token", None)
        if token is not None:
            self.token = token
        else:
            self.token = self.generate_token()

        # ensure priv is of type Privileges
        self.priv = priv if isinstance(priv, Privileges) else Privileges(priv)

        self.stats: dict[GameMode, ModeData] = {}
        self.status = Status()

        # userids, not player objects
        self.friends: set[int] = set()
        self.blocks: set[int] = set()

        self.channels: list[Channel] = []
        self.spectators: list[Player] = []
        self.spectating: Optional[Player] = None
        self.match: Optional[Match] = None
        self.stealth = False

        self.clan: Optional[Clan] = extras.get("clan")
        self.clan_priv: Optional[ClanPrivileges] = extras.get("clan_priv")

        self.achievements: set[Achievement] = set()

        self.geoloc: app.state.services.Geolocation = extras.get(
            "geoloc",
            {
                "latitude": 0.0,
                "longitude": 0.0,
                "country": {"acronym": "xx", "numeric": 0},
            },
        )

        self.utc_offset = extras.get("utc_offset", 0)
        self.pm_private = extras.get("pm_private", False)
        self.away_msg: Optional[str] = None
        self.silence_end = extras.get("silence_end", 0)
        self.donor_end = extras.get("donor_end", 0)
        self.in_lobby = False

        self.client_details: Optional[ClientDetails] = extras.get("client_details")
        self.pres_filter = PresenceFilter.Nil

        login_time = extras.get("login_time", 0.0)
        self.login_time = login_time
        self.last_recv_time = login_time

        # XXX: below is mostly implementation-specific & internal stuff

        # store most recent score for each gamemode.
        self.recent_scores: dict[GameMode, Optional[Score]] = {
            mode: None for mode in GameMode
        }

        # store the last beatmap /np'ed by the user.
        self.last_np: LastNp = {  # type: ignore
            "bmap": None,
            "mode_vn": None,
            "timeout": 0.0,
        }

        # TODO: document
        self.current_menu = MAIN_MENU
        self.previous_menus: list[Menu] = []

        # subject to possible change in the future,
        # although if anything, bot accounts will
        # probably just use the /api/ routes?
        self.bot_client = extras.get("bot_client", False)
        if self.bot_client:
            self.enqueue = lambda data: None  # type: ignore

        self.tourney_client = extras.get("tourney_client", False)

        self.api_key = extras.get("api_key", None)

        # packet queue
        self._queue = bytearray()

    def __repr__(self) -> str:
        return f"<{self.name} ({self.id})>"

    @property
    def online(self) -> bool:
        return self.token != ""

    @property
    def url(self) -> str:
        """The url to the player's profile."""
        return f"https://{app.settings.DOMAIN}/u/{self.id}"

    @property
    def embed(self) -> str:
        """An osu! chat embed to the player's profile."""
        return f"[{self.url} {self.name}]"

    @property
    def avatar_url(self) -> str:
        """The url to the player's avatar."""
        return f"https://a.{app.settings.DOMAIN}/{self.id}"

    @property
    def full_name(self) -> str:
        """The user's "full" name; including their clan tag."""
        if self.clan:
            return f"[{self.clan.tag}] {self.name}"
        else:
            return self.name

    # TODO: chat embed with clan tag hyperlinked?

    @property
    def remaining_silence(self) -> int:
        """The remaining time of the players silence."""
        return max(0, int(self.silence_end - time.time()))

    @property
    def silenced(self) -> bool:
        """Whether or not the player is silenced."""
        return self.remaining_silence != 0

    @cached_property
    def bancho_priv(self) -> ClientPrivileges:
        """The player's privileges according to the client."""
        ret = ClientPrivileges(0)
        if self.priv & Privileges.UNRESTRICTED:
            ret |= ClientPrivileges.PLAYER
        if self.priv & Privileges.DONATOR:
            ret |= ClientPrivileges.SUPPORTER
        if self.priv & Privileges.MODERATOR:
            ret |= ClientPrivileges.MODERATOR
        if self.priv & Privileges.ADMINISTRATOR:
            ret |= ClientPrivileges.DEVELOPER
        if self.priv & Privileges.DEVELOPER:
            ret |= ClientPrivileges.OWNER
        return ret

    @property
    def restricted(self) -> bool:
        """Return whether the player is restricted."""
        return not self.priv & Privileges.UNRESTRICTED

    @property
    def gm_stats(self) -> ModeData:
        """The player's stats in their currently selected mode."""
        return self.stats[self.status.mode]

    @property
    def recent_score(self) -> Optional[Score]:
        """The player's most recently submitted score."""
        score = None
        for s in self.recent_scores.values():
            if not s:
                continue

            if not score:
                score = s
                continue

            if s.server_time > score.server_time:
                score = s

        return score

    @staticmethod
    def generate_token() -> str:
        """Generate a random uuid as a token."""
        return str(uuid.uuid4())

    @staticmethod
    def make_safe(name: str) -> str:
        """Return a name safe for usage in sql."""
        return make_safe_name(name)

    def logout(self) -> None:
        """Log `self` out of the server."""
        # invalidate the user's token.
        self.token = ""

        # leave multiplayer.
        if self.match:
            self.leave_match()

        # stop spectating.
        if host := self.spectating:
            host.remove_spectator(self)

        # leave channels
        while self.channels:
            self.leave_channel(self.channels[0], kick=False)

        # remove from playerlist and
        # enqueue logout to all users.
        app.state.sessions.players.remove(self)

        if not self.restricted:
            if app.state.services.datadog:
                app.state.services.datadog.decrement("bancho.online_players")

            app.state.sessions.players.enqueue(app.packets.logout(self.id))

        log(f"{self} logged out.", Ansi.LYELLOW)

    async def update_privs(self, new: Privileges) -> None:
        """Update `self`'s privileges to `new`."""
        self.priv = new

        await app.state.services.database.execute(
            "UPDATE users SET priv = :priv WHERE id = :user_id",
            {"priv": self.priv, "user_id": self.id},
        )

        if "bancho_priv" in self.__dict__:
            del self.bancho_priv  # wipe cached_property

    async def add_privs(self, bits: Privileges) -> None:
        """Update `self`'s privileges, adding `bits`."""
        self.priv |= bits

        await app.state.services.database.execute(
            "UPDATE users SET priv = :priv WHERE id = :user_id",
            {"priv": self.priv, "user_id": self.id},
        )

        if "bancho_priv" in self.__dict__:
            del self.bancho_priv  # wipe cached_property

        if self.online:
            # if they're online, send a packet
            # to update their client-side privileges
            self.enqueue(app.packets.bancho_privileges(self.bancho_priv))

    async def remove_privs(self, bits: Privileges) -> None:
        """Update `self`'s privileges, removing `bits`."""
        self.priv &= ~bits

        await app.state.services.database.execute(
            "UPDATE users SET priv = :priv WHERE id = :user_id",
            {"priv": self.priv, "user_id": self.id},
        )

        if "bancho_priv" in self.__dict__:
            del self.bancho_priv  # wipe cached_property

        if self.online:
            # if they're online, send a packet
            # to update their client-side privileges
            self.enqueue(app.packets.bancho_privileges(self.bancho_priv))

    async def restrict(self, admin: Player, reason: str) -> None:
        """Restrict `self` for `reason`, and log to sql."""
        await self.remove_privs(Privileges.UNRESTRICTED)

        await app.state.services.database.execute(
            "INSERT INTO logs "
            "(`from`, `to`, `action`, `msg`, `time`) "
            "VALUES (:from, :to, :action, :msg, NOW())",
            {"from": admin.id, "to": self.id, "action": "restrict", "msg": reason},
        )

        for mode in (0, 1, 2, 3, 4, 5, 6, 8):
            await app.state.services.redis.zrem(
                f"bancho:leaderboard:{mode}",
                self.id,
            )
            await app.state.services.redis.zrem(
                f'bancho:leaderboard:{mode}:{self.geoloc["country"]["acronym"]}',
                self.id,
            )

        log_msg = f"{admin} restricted {self} for: {reason}."

        log(log_msg, Ansi.LRED)

        if webhook_url := app.settings.DISCORD_AUDIT_LOG_WEBHOOK:
            webhook = Webhook(webhook_url, content=log_msg)
            await webhook.post(app.state.services.http_client)

        # refresh their client state
        if self.online:
            self.logout()

    async def unrestrict(self, admin: Player, reason: str) -> None:
        """Restrict `self` for `reason`, and log to sql."""
        await self.add_privs(Privileges.UNRESTRICTED)

        await app.state.services.database.execute(
            "INSERT INTO logs "
            "(`from`, `to`, `action`, `msg`, `time`) "
            "VALUES (:from, :to, :action, :msg, NOW())",
            {"from": admin.id, "to": self.id, "action": "unrestrict", "msg": reason},
        )

        if not self.online:
            async with app.state.services.database.connection() as db_conn:
                await self.stats_from_sql_full(db_conn)

        for mode, stats in self.stats.items():
            await app.state.services.redis.zadd(
                f"bancho:leaderboard:{mode.value}",
                {str(self.id): stats.pp},
            )
            await app.state.services.redis.zadd(
                f"bancho:leaderboard:{mode.value}:{self.geoloc['country']['acronym']}",
                {str(self.id): stats.pp},
            )

        log_msg = f"{admin} unrestricted {self} for: {reason}."

        log(log_msg, Ansi.LRED)

        if webhook_url := app.settings.DISCORD_AUDIT_LOG_WEBHOOK:
            webhook = Webhook(webhook_url, content=log_msg)
            await webhook.post(app.state.services.http_client)

        if self.online:
            # log the user out if they're offline, this
            # will simply relog them and refresh their app.state
            self.logout()

    async def silence(self, admin: Player, duration: int, reason: str) -> None:
        """Silence `self` for `duration` seconds, and log to sql."""
        self.silence_end = int(time.time() + duration)

        await app.state.services.database.execute(
            "UPDATE users SET silence_end = :silence_end WHERE id = :user_id",
            {"silence_end": self.silence_end, "user_id": self.id},
        )

        await app.state.services.database.execute(
            "INSERT INTO logs "
            "(`from`, `to`, `action`, `msg`, `time`) "
            "VALUES (:from, :to, :action, :msg, NOW())",
            {"from": admin.id, "to": self.id, "action": "silence", "msg": reason},
        )

        # inform the user's client.
        self.enqueue(app.packets.silence_end(duration))

        # wipe their messages from any channels.
        app.state.sessions.players.enqueue(app.packets.user_silenced(self.id))

        # remove them from multiplayer match (if any).
        if self.match:
            self.leave_match()

        log(f"Silenced {self}.", Ansi.LCYAN)

    async def unsilence(self, admin: Player) -> None:
        """Unsilence `self`, and log to sql."""
        self.silence_end = int(time.time())

        await app.state.services.database.execute(
            "UPDATE users SET silence_end = :silence_end WHERE id = :user_id",
            {"silence_end": self.silence_end, "user_id": self.id},
        )

        await app.state.services.database.execute(
            "INSERT INTO logs "
            "(`from`, `to`, `action`, `msg`, `time`) "
            "VALUES (:from, :to, :action, NULL, NOW())",
            {"from": admin.id, "to": self.id, "action": "unsilence"},
        )

        # inform the user's client
        self.enqueue(app.packets.silence_end(0))

        log(f"Unsilenced {self}.", Ansi.LCYAN)

    def join_match(self, m: Match, passwd: str) -> bool:
        """Attempt to add `self` to `m`."""
        if self.match:
            log(f"{self} tried to join multiple matches?")
            self.enqueue(app.packets.match_join_fail())
            return False

        if self.id in m.tourney_clients:
            # the user is already in the match with a tourney client.
            # users cannot spectate themselves so this is not possible.
            self.enqueue(app.packets.match_join_fail())
            return False

        if self is not m.host:
            # match already exists, we're simply joining.
            # NOTE: staff members have override to pw and can
            # simply use any to join a pw protected match.
            if passwd != m.passwd and self not in app.state.sessions.players.staff:
                log(f"{self} tried to join {m} w/ incorrect pw.", Ansi.LYELLOW)
                self.enqueue(app.packets.match_join_fail())
                return False
            if (slotID := m.get_free()) is None:
                log(f"{self} tried to join a full match.", Ansi.LYELLOW)
                self.enqueue(app.packets.match_join_fail())
                return False

        else:
            # match is being created
            slotID = 0

        if not self.join_channel(m.chat):
            log(f"{self} failed to join {m.chat}.", Ansi.LYELLOW)
            return False

        if (lobby := app.state.sessions.channels["#lobby"]) in self.channels:
            self.leave_channel(lobby)

        slot: Slot = m.slots[0 if slotID == -1 else slotID]

        # if in a teams-vs mode, switch team from neutral to red.
        if m.team_type in (MatchTeamTypes.team_vs, MatchTeamTypes.tag_team_vs):
            slot.team = MatchTeams.red

        slot.status = SlotStatus.not_ready
        slot.player = self
        self.match = m

        self.enqueue(app.packets.match_join_success(m))
        m.enqueue_state()

        return True

    def leave_match(self) -> None:
        """Attempt to remove `self` from their match."""
        if not self.match:
            if app.settings.DEBUG:
                log(f"{self} tried leaving a match they're not in?", Ansi.LYELLOW)
            return

        slot = self.match.get_slot(self)
        assert slot is not None

        if slot.status == SlotStatus.locked:
            # player was kicked, keep the slot locked.
            new_status = SlotStatus.locked
        else:
            # player left, open the slot for new players to join.
            new_status = SlotStatus.open

        slot.reset(new_status=new_status)

        self.leave_channel(self.match.chat)

        if all(slot.empty() for slot in self.match.slots):
            # multi is now empty, chat has been removed.
            # remove the multi from the channels list.
            log(f"Match {self.match} finished.")

            # cancel any pending start timers
            if self.match.starting["start"] is not None:
                self.match.starting["start"].cancel()
                for alert in self.match.starting["alerts"]:
                    alert.cancel()

                # i guess unnecessary but i'm ocd
                self.match.starting["start"] = None
                self.match.starting["alerts"] = None
                self.match.starting["time"] = None

            app.state.sessions.matches.remove(self.match)

            if lobby := app.state.sessions.channels["#lobby"]:
                lobby.enqueue(app.packets.dispose_match(self.match.id))

        else:  # multi is not empty
            if self is self.match.host:
                # player was host, trasnfer to first occupied slot
                for s in self.match.slots:
                    if s.status & SlotStatus.has_player:
                        self.match.host_id = s.player.id
                        self.match.host.enqueue(app.packets.match_transfer_host())
                        break

            if self in self.match._refs:
                self.match._refs.remove(self)
                self.match.chat.send_bot(f"{self.name} removed from match referees.")

            # notify others of our deprature
            self.match.enqueue_state()

        self.match = None

    async def join_clan(self, c: "Clan") -> bool:
        """Attempt to add `self` to `c`."""
        if self.id in c.member_ids:
            return False

        if not "invited":  # TODO
            return False

        await c.add_member(self)
        return True

    async def leave_clan(self) -> None:
        """Attempt to remove `self` from `c`."""
        if not self.clan:
            return

        await self.clan.remove_member(self)

    def join_channel(self, c: Channel) -> bool:
        """Attempt to add `self` to `c`."""
        if (
            self in c
            or not c.can_read(self.priv)  # player already in channel
            or c._name == "#lobby"  # no read privs
            and not self.in_lobby  # not in mp lobby
        ):
            return False

        c.append(self)  # add to c.players
        self.channels.append(c)  # add to p.channels

        self.enqueue(app.packets.channel_join(c.name))

        chan_info_packet = app.packets.channel_info(c.name, c.topic, len(c.players))

        if c.instance:
            # instanced channel, only send the players
            # who are currently inside the instance
            for p in c.players:
                p.enqueue(chan_info_packet)
        else:
            # normal channel, send to all players who
            # have access to see the channel's usercount.
            for p in app.state.sessions.players:
                if c.can_read(p.priv):
                    p.enqueue(chan_info_packet)

        if app.settings.DEBUG:
            log(f"{self} joined {c}.")

        return True

    def leave_channel(self, c: Channel, kick: bool = True) -> None:
        """Attempt to remove `self` from `c`."""
        # ensure they're in the chan.
        if self not in c:
            return

        c.remove(self)  # remove from c.players
        self.channels.remove(c)  # remove from p.channels

        if kick:
            self.enqueue(app.packets.channel_kick(c.name))

        chan_info_packet = app.packets.channel_info(c.name, c.topic, len(c.players))

        if c.instance:
            # instanced channel, only send the players
            # who are currently inside the instance
            for p in c.players:
                p.enqueue(chan_info_packet)
        else:
            # normal channel, send to all players who
            # have access to see the channel's usercount.
            for p in app.state.sessions.players:
                if c.can_read(p.priv):
                    p.enqueue(chan_info_packet)

        if app.settings.DEBUG:
            log(f"{self} left {c}.")

    def add_spectator(self, p: Player) -> None:
        """Attempt to add `p` to `self`'s spectators."""
        chan_name = f"#spec_{self.id}"

        if not (spec_chan := app.state.sessions.channels[chan_name]):
            # spectator chan doesn't exist, create it.
            spec_chan = Channel(
                name=chan_name,
                topic=f"{self.name}'s spectator channel.",
                auto_join=False,
                instance=True,
            )

            self.join_channel(spec_chan)
            app.state.sessions.channels.append(spec_chan)

        # attempt to join their spectator channel.
        if not p.join_channel(spec_chan):
            log(f"{self} failed to join {spec_chan}?", Ansi.LYELLOW)
            return

        if not p.stealth:
            p_joined = app.packets.fellow_spectator_joined(p.id)
            for s in self.spectators:
                s.enqueue(p_joined)
                p.enqueue(app.packets.fellow_spectator_joined(s.id))

            self.enqueue(app.packets.spectator_joined(p.id))
        else:
            # player is admin in stealth, only give
            # other players data to us, not vice-versa.
            for s in self.spectators:
                p.enqueue(app.packets.fellow_spectator_joined(s.id))

        self.spectators.append(p)
        p.spectating = self

        log(f"{p} is now spectating {self}.")

    def remove_spectator(self, p: Player) -> None:
        """Attempt to remove `p` from `self`'s spectators."""
        self.spectators.remove(p)
        p.spectating = None

        c = app.state.sessions.channels[f"#spec_{self.id}"]
        p.leave_channel(c)

        if not self.spectators:
            # remove host from channel, deleting it.
            self.leave_channel(c)
        else:
            # send new playercount
            c_info = app.packets.channel_info(c.name, c.topic, len(c.players))
            fellow = app.packets.fellow_spectator_left(p.id)

            self.enqueue(c_info)

            for s in self.spectators:
                s.enqueue(fellow + c_info)

        self.enqueue(app.packets.spectator_left(p.id))
        log(f"{p} is no longer spectating {self}.")

    async def add_friend(self, p: Player) -> None:
        """Attempt to add `p` to `self`'s friends."""
        if p.id in self.friends:
            log(f"{self} tried to add {p}, who is already their friend!", Ansi.LYELLOW)
            return

        self.friends.add(p.id)
        await app.state.services.database.execute(
            "REPLACE INTO relationships (user1, user2, type) VALUES (:user1, :user2, 'friend')",
            {"user1": self.id, "user2": p.id},
        )

        log(f"{self} friended {p}.")

    async def remove_friend(self, p: Player) -> None:
        """Attempt to remove `p` from `self`'s friends."""
        if p.id not in self.friends:
            log(f"{self} tried to unfriend {p}, who is not their friend!", Ansi.LYELLOW)
            return

        self.friends.remove(p.id)
        await app.state.services.database.execute(
            "DELETE FROM relationships WHERE user1 = :user1 AND user2 = :user2",
            {"user1": self.id, "user2": p.id},
        )

        log(f"{self} unfriended {p}.")

    async def add_block(self, p: Player) -> None:
        """Attempt to add `p` to `self`'s blocks."""
        if p.id in self.blocks:
            log(
                f"{self} tried to block {p}, who they've already blocked!",
                Ansi.LYELLOW,
            )
            return

        self.blocks.add(p.id)
        await app.state.services.database.execute(
            "REPLACE INTO relationships VALUES (:user1, :user2, 'block')",
            {"user1": self.id, "user2": p.id},
        )

        log(f"{self} blocked {p}.")

    async def remove_block(self, p: Player) -> None:
        """Attempt to remove `p` from `self`'s blocks."""
        if p.id not in self.blocks:
            log(f"{self} tried to unblock {p}, who they haven't blocked!", Ansi.LYELLOW)
            return

        self.blocks.remove(p.id)
        await app.state.services.database.execute(
            "DELETE FROM relationships WHERE user1 = :user1 AND user2 = :user2",
            {"user1": self.id, "user2": p.id},
        )

        log(f"{self} unblocked {p}.")

    async def unlock_achievement(self, a: "Achievement") -> None:
        """Unlock `ach` for `self`, storing in both cache & sql."""
        await app.state.services.database.execute(
            "INSERT INTO user_achievements (userid, achid) VALUES (:user_id, :ach_id)",
            {"user_id": self.id, "ach_id": a.id},
        )

        self.achievements.add(a)

    async def relationships_from_sql(self, db_conn: databases.core.Connection) -> None:
        """Retrieve `self`'s relationships from sql."""
        for row in await db_conn.fetch_all(
            "SELECT user2, type FROM relationships WHERE user1 = :user1",
            {"user1": self.id},
        ):
            if row["type"] == "friend":
                self.friends.add(row["user2"])
            else:
                self.blocks.add(row["user2"])

        # always have bot added to friends.
        self.friends.add(1)

    async def achievements_from_sql(self, db_conn: databases.core.Connection) -> None:
        """Retrieve `self`'s achievements from sql."""
        for row in await db_conn.fetch_all(
            "SELECT ua.achid id FROM user_achievements ua "
            "INNER JOIN achievements a ON a.id = ua.achid "
            "WHERE ua.userid = :user_id",
            {"user_id": self.id},
        ):
            for ach in app.state.sessions.achievements:
                if row["id"] == ach.id:
                    self.achievements.add(ach)

    async def get_global_rank(self, mode: GameMode) -> int:
        if self.restricted:
            return 0

        rank = await app.state.services.redis.zrevrank(
            f"bancho:leaderboard:{mode.value}",
            str(self.id),
        )
        return rank + 1 if rank is not None else 0

    async def get_country_rank(self, mode: GameMode) -> int:
        if self.restricted:
            return 0

        country = self.geoloc["country"]["acronym"]
        rank = await app.state.services.redis.zrevrank(
            f"bancho:leaderboard:{mode.value}:{country}",
            str(self.id),
        )

        return rank + 1 if rank is not None else 0

    async def update_rank(self, mode: GameMode) -> int:
        country = self.geoloc["country"]["acronym"]
        stats = self.stats[mode]

        if not self.restricted:
            # global rank
            await app.state.services.redis.zadd(
                f"bancho:leaderboard:{mode.value}",
                {str(self.id): stats.pp},
            )

            # country rank
            await app.state.services.redis.zadd(
                f"bancho:leaderboard:{mode.value}:{country}",
                {str(self.id): stats.pp},
            )

        return await self.get_global_rank(mode)

    async def stats_from_sql_full(self, db_conn: databases.core.Connection) -> None:
        """Retrieve `self`'s stats (all modes) from sql."""
        for row in await db_conn.fetch_all(
            "SELECT mode, tscore, rscore, pp, acc, "
            "plays, playtime, max_combo, total_hits, "
            "xh_count, x_count, sh_count, s_count, a_count "
            "FROM stats "
            "WHERE id = :user_id",
            {"user_id": self.id},
        ):
            row = dict(row)  # make mutable copy
            mode = row.pop("mode")

            # calculate player's rank.
            row["rank"] = await self.get_global_rank(GameMode(mode))

            row["grades"] = {
                Grade.XH: row.pop("xh_count"),
                Grade.X: row.pop("x_count"),
                Grade.SH: row.pop("sh_count"),
                Grade.S: row.pop("s_count"),
                Grade.A: row.pop("a_count"),
            }

            self.stats[GameMode(mode)] = ModeData(**row)

    def send_menu_clear(self) -> None:
        """Clear the user's osu! chat with the bot
        to make room for a new menu to be sent."""
        # NOTE: the only issue with this is that it will
        # wipe any messages the client can see from the bot
        # (including any other channels). perhaps menus can
        # be sent from a separate presence to prevent this?
        self.enqueue(app.packets.user_silenced(app.state.sessions.bot.id))

    def send_current_menu(self) -> None:
        """Forward a standardized form of the user's
        current menu to them via the osu! chat."""
        msg = [self.current_menu.name]

        for key, (cmd, data) in self.current_menu.options.items():
            val = data.name if data else "Back"
            msg.append(f"[osump://{key}/ {val}]")

        chat_height = 10
        lines_used = len(msg)
        if lines_used < chat_height:
            msg += [chr(8192)] * (chat_height - lines_used)

        self.send_menu_clear()
        self.send_bot("\n".join(msg))

    def update_latest_activity_soon(self) -> None:
        """Update the player's latest activity in the database."""
        task = app.state.services.database.execute(
            "UPDATE users SET latest_activity = UNIX_TIMESTAMP() WHERE id = :user_id",
            {"user_id": self.id},
        )
        app.state.loop.create_task(task)

    def enqueue(self, data: bytes) -> None:
        """Add data to be sent to the client."""
        self._queue += data

    def dequeue(self) -> Optional[bytes]:
        """Get data from the queue to send to the client."""
        if self._queue:
            data = bytes(self._queue)
            self._queue.clear()
            return data

        return None

    def send(self, msg: str, sender: Player, chan: Optional[Channel] = None) -> None:
        """Enqueue `sender`'s `msg` to `self`. Sent in `chan`, or dm."""
        self.enqueue(
            app.packets.send_message(
                sender=sender.name,
                msg=msg,
                recipient=(chan or self).name,
                sender_id=sender.id,
            ),
        )

    def send_bot(self, msg: str) -> None:
        """Enqueue `msg` to `self` from bot."""
        bot = app.state.sessions.bot

        self.enqueue(
            app.packets.send_message(
                sender=bot.name,
                msg=msg,
                recipient=self.name,
                sender_id=bot.id,
            ),
        )
