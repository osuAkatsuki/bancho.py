from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date
from enum import IntEnum
from enum import unique
from functools import cached_property
from typing import Literal
from typing import Mapping
from typing import MutableMapping
from typing import Optional
from typing import TYPE_CHECKING
from typing import TypedDict

import app.objects.geolocation
import app.packets
import app.settings
import app.state.services
from app._typing import IPAddress
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.constants.privileges import ClientPrivileges
from app.constants.privileges import Privileges
from app.objects.match import Match
from app.objects.menu import Menu
from app.objects.menu import MenuCommands
from app.objects.menu import MenuFunction
from app.objects.score import Grade
from app.utils import escape_enum
from app.utils import make_safe_name
from app.utils import pymysql_encode

if TYPE_CHECKING:
    from app.objects.beatmap import Beatmap
    from app.objects.channel import Channel

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


# TODO: split Account & Player up into more specialized classes for things
#       like tournament manager & spectator clients, and bots.


class Account:
    def __init__(
        self,
        id: int,
        name: str,
        priv: int,
        pw_bcrypt: Optional[str | bytes] = None,
        stats: Optional[Mapping[GameMode, ModeData]] = None,
        friends: Optional[set[int]] = None,
        blocks: Optional[set[int]] = None,
        clan_id: Optional[int] = None,
        clan_priv: Optional[int] = None,
        achievement_ids: Optional[set[int]] = None,
        silence_end: int = 0,
        donor_end: int = 0,
        api_key: Optional[str] = None,
    ) -> None:
        self.id = id
        self.name = name
        self.priv = priv  # TODO: rename to privileges

        if pw_bcrypt is not None:
            # support both str and bytes
            if isinstance(pw_bcrypt, str):
                self.pw_bcrypt = pw_bcrypt.encode()
            elif isinstance(pw_bcrypt, bytes):
                self.pw_bcrypt = pw_bcrypt
            else:
                raise NotImplementedError(
                    "Player.pw_bcrypt parameter only supports `str | bytes`.",
                )
        else:
            self.pw_bcrypt = None

        self.stats = stats or {}

        # userids, not player objects
        self.friends = friends or set()
        self.blocks = blocks or set()

        self.clan_id = clan_id
        self.clan_priv = clan_priv

        self.achievement_ids = achievement_ids or set()

        self.silence_end = silence_end
        self.donor_end = donor_end

        self.api_key = api_key

    @property
    def safe_name(self) -> str:
        return make_safe_name(self.name)


class Player(Account):
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
        token: Optional[str] = None,
        status: Optional[Status] = None,
        channels: Optional[list[Channel]] = None,
        spectators: Optional[list[Player]] = None,
        spectating: Optional[Player] = None,
        match: Optional[Match] = None,
        geoloc: Optional[app.objects.geolocation.Geolocation] = None,
        utc_offset: int = 0,
        pm_private: bool = False,  # TODO: should this be under Account?
        away_msg: Optional[str] = None,  # TODO: should this be under Account?
        in_lobby: bool = False,
        client_details: Optional[ClientDetails] = None,
        pres_filter: PresenceFilter = PresenceFilter.Nil,
        login_time: float = 0.0,
        last_recv_time: float = 0.0,
        recent_score_ids: Optional[MutableMapping[GameMode, Optional[int]]] = None,
        last_np: Optional[LastNp] = None,
        current_menu: Optional[Menu] = None,
        previous_menus: Optional[list[Menu]] = None,
        bot_client: bool = False,
        tourney_client: bool = False,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

        self.token = token
        self.status = status or Status()

        self.channels = channels or []
        self.spectators = spectators or []
        self.spectating = spectating or None
        self.match = match or None

        # TODO: store geolocation {ip:geoloc} store as a repository, store ip reference in other objects
        self.geoloc = geoloc or {
            "latitude": 0.0,
            "longitude": 0.0,
            "country": {"acronym": "xx", "numeric": 0},
        }

        self.utc_offset = utc_offset
        self.pm_private = pm_private
        self.away_msg = away_msg
        self.in_lobby = in_lobby

        self.client_details = client_details
        self.pres_filter = pres_filter

        self.login_time = login_time
        self.last_recv_time = last_recv_time  # or login_time

        # XXX: below is mostly implementation-specific & internal stuff

        # store most recent score for each gamemode.
        self.recent_score_ids = recent_score_ids or {mode: None for mode in GameMode}

        # store the last beatmap /np'ed by the user.
        self.last_np = last_np

        # TODO: documentation for menus
        self.current_menu = current_menu
        self.previous_menus = previous_menus or []

        # subject to change in the future
        self.bot_client = bot_client
        self.tourney_client = tourney_client

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

    # TODO: chat embed with clan tag hyperlinked?

    @property
    def remaining_silence(self) -> int:
        """The remaining time of the players silence."""
        return max(0, int(self.silence_end - time.time()))

    @property
    def silenced(self) -> bool:
        """Whether or not the player is silenced."""
        return self.remaining_silence != 0

    @property
    def bancho_priv(self) -> int:
        """The player's privileges according to the client."""
        priv_bits = 0
        if self.priv & Privileges.UNRESTRICTED:
            priv_bits |= ClientPrivileges.PLAYER
        if self.priv & Privileges.DONATOR:
            priv_bits |= ClientPrivileges.SUPPORTER
        if self.priv & Privileges.MODERATOR:
            priv_bits |= ClientPrivileges.MODERATOR
        if self.priv & Privileges.ADMINISTRATOR:
            priv_bits |= ClientPrivileges.DEVELOPER
        if self.priv & Privileges.DEVELOPER:
            priv_bits |= ClientPrivileges.OWNER
        return priv_bits

    @property
    def restricted(self) -> bool:
        """Return whether the player is restricted."""
        return not self.priv & Privileges.UNRESTRICTED

    @property
    def gm_stats(self) -> ModeData:
        """The player's stats in their currently selected mode."""
        return self.stats[self.status.mode]

    @property  # TODO: should this be in repos, or usecases?
    def recent_score_id(self) -> Optional[int]:
        """The player's most recently submitted score."""
        return self.recent_score_ids.get(self.status.mode)

    # TODO: from_row, to_row?

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
