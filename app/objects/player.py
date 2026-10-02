from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import date
from enum import IntEnum
from enum import StrEnum
from enum import unique
from functools import cached_property
from typing import TYPE_CHECKING
from typing import TypedDict

import app.packets
import app.settings
from app._typing import IPAddress
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.constants.privileges import ClientPrivileges
from app.constants.privileges import Privileges
from app.objects.channel import Channel
from app.objects.match import Match
from app.objects.score import Grade
from app.objects.score import Score
from app.utils import escape_enum
from app.utils import make_safe_name
from app.utils import pymysql_encode

if TYPE_CHECKING:
    from app.constants.privileges import ClanPrivileges
    from app.objects.beatmap import Beatmap
    from app.objects.score import Score
    from app.runtime import Geolocation


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
    mods: Mods | None
    timeout: float


class OsuStream(StrEnum):
    STABLE = "stable"
    BETA = "beta"
    CUTTINGEDGE = "cuttingedge"
    TOURNEY = "tourney"
    DEV = "dev"


WINE_ADAPTER_SENTINEL = "runningunderwine"


class OsuVersion:
    # b20200201.2cuttingedge
    # date = 2020/02/01
    # revision = 2
    # stream = cuttingedge
    def __init__(
        self,
        date: date,
        revision: int | None,  # TODO: should this be optional?
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
        adapters_string = ".".join(self.adapters)
        if adapters_string != WINE_ADAPTER_SENTINEL:
            # Normal clients send adapter lists with a trailing ".".
            adapters_string += "."

        return (
            f"{self.osu_path_md5}:{adapters_string}"
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

    is_bot_client: `bool`
        Whether this is a bot account.

    is_tourney_client: `bool`
        Whether this is a management/spectator tourney client.

    _packet_queue: `list[bytes]`
        Bytes enqueued to the player which will be transmitted
        at the tail end of their next connection to the server.
        XXX: cls.enqueue() will add data to this queue, and
             cls.dequeue() will return the data, and remove it.
    """

    def __init__(
        self,
        id: int,
        name: str,
        priv: Privileges,
        pw_bcrypt: bytes | None,
        token: str,
        clan_id: int | None = None,
        clan_priv: ClanPrivileges | None = None,
        geoloc: Geolocation | None = None,
        utc_offset: int = 0,
        pm_private: bool = False,
        silence_end: int = 0,
        donor_end: int = 0,
        client_details: ClientDetails | None = None,
        login_time: float = 0.0,
        is_bot_client: bool = False,
        is_tourney_client: bool = False,
        api_key: str | None = None,
    ) -> None:
        if geoloc is None:
            geoloc = {
                "latitude": 0.0,
                "longitude": 0.0,
                "country": {"acronym": "xx", "numeric": 0},
            }

        self.id = id
        self.name = name
        self.priv = priv
        self.pw_bcrypt = pw_bcrypt
        self.token = token
        self.clan_id = clan_id
        self.clan_priv = clan_priv
        self.geoloc = geoloc
        self.utc_offset = utc_offset
        self.pm_private = pm_private
        self.silence_end = silence_end
        self.donor_end = donor_end
        self.client_details = client_details
        self.login_time = login_time
        self.last_recv_time = login_time
        self.is_bot_client = is_bot_client
        self.is_tourney_client = is_tourney_client
        self.api_key = api_key

        # avoid enqueuing packets to bot accounts.
        if self.is_bot_client:

            def _noop_enqueue(data: bytes) -> None:
                pass

            self.enqueue = _noop_enqueue  # type: ignore[method-assign]

        self.away_msg: str | None = None
        self.in_lobby = False

        self.stats: dict[GameMode, ModeData] = {}
        self.status = Status()

        # userids, not player objects
        self.friends: set[int] = set()
        self.blocks: set[int] = set()

        self.channels: list[Channel] = []
        self.spectators: list[Player] = []
        self.spectating: Player | None = None
        self.match: Match | None = None
        self.stealth = False

        self.pres_filter = PresenceFilter.Nil

        # store most recent score for each gamemode.
        self.recent_scores: dict[GameMode, Score | None] = {
            mode: None for mode in GameMode
        }

        # store the last beatmap /np'ed by the user.
        self.last_np: LastNp | None = None

        self._packet_queue: list[bytes] = []

    def __repr__(self) -> str:
        return f"<{self.name} ({self.id})>"

    @property
    def safe_name(self) -> str:
        return make_safe_name(self.name)

    @property
    def is_online(self) -> bool:
        return bool(self.token != "")

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
    def recent_score(self) -> Score | None:
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

    def enqueue(self, data: bytes) -> None:
        """Add data to be sent to the client."""
        self._packet_queue.append(data)

    def dequeue(self) -> bytes | None:
        """Get data from the queue to send to the client."""
        if self._packet_queue:
            data = b"".join(self._packet_queue)
            self._packet_queue.clear()
            return data

        return None

    def send(self, msg: str, sender: Player, chan: Channel | None = None) -> None:
        """Enqueue `sender`'s `msg` to `self`. Sent in `chan`, or dm."""
        self.enqueue(
            app.packets.send_message(
                sender=sender.name,
                msg=msg,
                recipient=(chan or self).name,
                sender_id=sender.id,
            ),
        )
