from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date
from enum import IntEnum
from enum import unique
from functools import cached_property
from typing import Any
from typing import Literal
from typing import Optional
from typing import TYPE_CHECKING
from typing import TypedDict
from typing import Union

import app.packets
import app.settings
import app.state
from app._typing import IPAddress
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.constants.privileges import ClientPrivileges
from app.constants.privileges import Privileges
from app.objects.channel import Channel
from app.objects.match import Match
from app.objects.menu import Menu
from app.objects.menu import menu_keygen
from app.objects.menu import MenuCommands
from app.objects.menu import MenuFunction
from app.objects.score import Grade
from app.objects.score import Score
from app.utils import escape_enum
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


class OsuVersion:
    # b20200201.2cuttingedge
    # date = 2020/02/01
    # revision = 2
    # stream = cuttingedge
    def __init__(
        self,
        date: date,
        revision: Optional[int],  # TODO: should this be optional?
        stream: Literal["stable", "beta", "cuttingedge", "tourney", "dev"],
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

    __slots__ = (
        "token",
        "id",
        "name",
        "safe_name",
        "pw_bcrypt",
        "priv",
        "stats",
        "status",
        "friends",
        "blocks",
        "channels",
        "spectators",
        "spectating",
        "match",
        "stealth",
        "clan",
        "clan_priv",
        "achievements",
        "recent_scores",
        "last_np",
        "location",
        "utc_offset",
        "pm_private",
        "away_msg",
        "silence_end",
        "in_lobby",
        "client_details",
        "pres_filter",
        "login_time",
        "last_recv_time",
        "current_menu",
        "previous_menus",
        "bot_client",
        "tourney_client",
        "api_key",
        "_queue",
        "__dict__",
    )

    def __init__(
        self,
        id: int,
        name: str,
        priv: Union[int, Privileges],
        token: Optional[str] = None,
        **extras: Any,
    ) -> None:
        self.id = id
        self.name = name
        self.safe_name = self.make_safe(self.name)

        if pw_bcrypt := extras.get("pw_bcrypt"):
            if isinstance(pw_bcrypt, str):
                self.pw_bcrypt = pw_bcrypt.encode()
            elif isinstance(pw_bcrypt, bytes):
                self.pw_bcrypt = pw_bcrypt
            else:
                raise NotImplementedError
        else:
            self.pw_bcrypt = None

        self.token = token

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

        self.tourney_client = extras.get("tourney_client", False)

        self.api_key = extras.get("api_key", None)

        # packet queue
        self._queue = bytearray()

    def __repr__(self) -> str:
        return f"<{self.name} ({self.id})>"

    @cached_property
    def online(self) -> bool:
        return self.token != ""

    @cached_property
    def url(self) -> str:
        """The url to the player's profile."""
        # NOTE: this is currently never wiped because
        # domain & id cannot be changed in-game; if this
        # ever changes, it will need to be wiped.
        return f"https://{app.settings.DOMAIN}/u/{self.id}"

    @cached_property
    def embed(self) -> str:
        """An osu! chat embed to the player's profile."""
        # NOTE: this is currently never wiped because
        # url & name cannot be changed in-game; if this
        # ever changes, it will need to be wiped.
        return f"[{self.url} {self.name}]"

    @cached_property
    def avatar_url(self) -> str:
        """The url to the player's avatar."""
        # NOTE: this is currently never wiped because
        # domain & id cannot be changed in-game; if this
        # ever changes, it will need to be wiped.
        return f"https://a.{app.settings.DOMAIN}/{self.id}"

    @cached_property
    def full_name(self) -> str:
        """The user's "full" name; including their clan tag."""
        # NOTE: this is currently only wiped when the
        # user leaves their clan; if name/clantag ever
        # become changeable, it will need to be wiped.
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
        if self.priv & Privileges.NORMAL:
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

    @cached_property
    def restricted(self) -> bool:
        """Return whether the player is restricted."""
        return not self.priv & Privileges.NORMAL

    @property
    def gm_stats(self) -> ModeData:
        """The player's stats in their currently selected mode."""
        return self.stats[self.status.mode]

    @cached_property  # TODO: should this be in repos, or usecases?
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
    def make_safe(name: str) -> str:
        """Return a name safe for usage in sql."""
        return name.lower().replace(" ", "_")

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
