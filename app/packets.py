from __future__ import annotations

import random
import struct
from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from dataclasses import field
from enum import IntEnum
from enum import unique
from functools import cache
from functools import lru_cache
from typing import Any
from typing import Callable
from typing import Collection
from typing import Iterator
from typing import NamedTuple
from typing import Optional
from typing import TYPE_CHECKING
from typing import Union

# from app.objects.beatmap import BeatmapInfo

if TYPE_CHECKING:
    from app.objects.match import Match
    from app.objects.player import Player

# tuple of some of struct's format specifiers
# for clean access within packet pack/unpack.


@unique
class ClientPackets(IntEnum):
    CHANGE_ACTION = 0
    SEND_PUBLIC_MESSAGE = 1
    LOGOUT = 2
    REQUEST_STATUS_UPDATE = 3
    PING = 4
    START_SPECTATING = 16
    STOP_SPECTATING = 17
    SPECTATE_FRAMES = 18
    ERROR_REPORT = 20
    CANT_SPECTATE = 21
    SEND_PRIVATE_MESSAGE = 25
    PART_LOBBY = 29
    JOIN_LOBBY = 30
    CREATE_MATCH = 31
    JOIN_MATCH = 32
    PART_MATCH = 33
    MATCH_CHANGE_SLOT = 38
    MATCH_READY = 39
    MATCH_LOCK = 40
    MATCH_CHANGE_SETTINGS = 41
    MATCH_START = 44
    MATCH_SCORE_UPDATE = 47
    MATCH_COMPLETE = 49
    MATCH_CHANGE_MODS = 51
    MATCH_LOAD_COMPLETE = 52
    MATCH_NO_BEATMAP = 54
    MATCH_NOT_READY = 55
    MATCH_FAILED = 56
    MATCH_HAS_BEATMAP = 59
    MATCH_SKIP_REQUEST = 60
    CHANNEL_JOIN = 63
    BEATMAP_INFO_REQUEST = 68
    MATCH_TRANSFER_HOST = 70
    FRIEND_ADD = 73
    FRIEND_REMOVE = 74
    MATCH_CHANGE_TEAM = 77
    CHANNEL_PART = 78
    RECEIVE_UPDATES = 79
    SET_AWAY_MESSAGE = 82
    IRC_ONLY = 84
    USER_STATS_REQUEST = 85
    MATCH_INVITE = 87
    MATCH_CHANGE_PASSWORD = 90
    TOURNAMENT_MATCH_INFO_REQUEST = 93
    USER_PRESENCE_REQUEST = 97
    USER_PRESENCE_REQUEST_ALL = 98
    TOGGLE_BLOCK_NON_FRIEND_DMS = 99
    TOURNAMENT_JOIN_MATCH_CHANNEL = 108
    TOURNAMENT_LEAVE_MATCH_CHANNEL = 109

    def __repr__(self) -> str:
        return f"<{self.name} ({self.value})>"


@unique
class ServerPackets(IntEnum):
    USER_ID = 5
    SEND_MESSAGE = 7
    PONG = 8
    HANDLE_IRC_CHANGE_USERNAME = 9  # unused
    HANDLE_IRC_QUIT = 10
    USER_STATS = 11
    USER_LOGOUT = 12
    SPECTATOR_JOINED = 13
    SPECTATOR_LEFT = 14
    SPECTATE_FRAMES = 15
    VERSION_UPDATE = 19
    SPECTATOR_CANT_SPECTATE = 22
    GET_ATTENTION = 23
    NOTIFICATION = 24
    UPDATE_MATCH = 26
    NEW_MATCH = 27
    DISPOSE_MATCH = 28
    TOGGLE_BLOCK_NON_FRIEND_DMS = 34
    MATCH_JOIN_SUCCESS = 36
    MATCH_JOIN_FAIL = 37
    FELLOW_SPECTATOR_JOINED = 42
    FELLOW_SPECTATOR_LEFT = 43
    ALL_PLAYERS_LOADED = 45
    MATCH_START = 46
    MATCH_SCORE_UPDATE = 48
    MATCH_TRANSFER_HOST = 50
    MATCH_ALL_PLAYERS_LOADED = 53
    MATCH_PLAYER_FAILED = 57
    MATCH_COMPLETE = 58
    MATCH_SKIP = 61
    UNAUTHORIZED = 62  # unused
    CHANNEL_JOIN_SUCCESS = 64
    CHANNEL_INFO = 65
    CHANNEL_KICK = 66
    CHANNEL_AUTO_JOIN = 67
    BEATMAP_INFO_REPLY = 69
    PRIVILEGES = 71
    FRIENDS_LIST = 72
    PROTOCOL_VERSION = 75
    MAIN_MENU_ICON = 76
    MONITOR = 80  # unused
    MATCH_PLAYER_SKIPPED = 81
    USER_PRESENCE = 83
    RESTART = 86
    MATCH_INVITE = 88
    CHANNEL_INFO_END = 89
    MATCH_CHANGE_PASSWORD = 91
    SILENCE_END = 92
    USER_SILENCED = 94
    USER_PRESENCE_SINGLE = 95
    USER_PRESENCE_BUNDLE = 96
    USER_DM_BLOCKED = 100
    TARGET_IS_SILENCED = 101
    VERSION_UPDATE_FORCED = 102
    SWITCH_SERVER = 103
    ACCOUNT_RESTRICTED = 104
    RTX = 105  # unused
    MATCH_ABORT = 106
    SWITCH_TOURNAMENT_SERVER = 107

    def __repr__(self) -> str:
        return f"<{self.name} ({self.value})>"


# TODO: clean this up
@unique
class osuTypes(IntEnum):
    # integral
    i8 = 0
    u8 = 1
    i16 = 2
    u16 = 3
    i32 = 4
    u32 = 5
    f32 = 6
    i64 = 7
    u64 = 8
    f64 = 9

    # osu
    message = 11
    channel = 12
    match = 13
    scoreframe = 14
    mapInfoRequest = 15
    mapInfoReply = 16
    replayFrameBundle = 17

    # misc
    i32_list = 18  # 2 bytes len
    i32_list4l = 19  # 4 bytes len
    string = 20
    raw = 21


class Message(NamedTuple):
    sender: str
    text: str
    recipient: str
    sender_id: int


class Channel(NamedTuple):
    name: str
    topic: str
    players: int


class ReplayAction(IntEnum):
    Standard = 0
    NewSong = 1
    Skip = 2
    Completion = 3
    Fail = 4
    Pause = 5
    Unpause = 6
    SongSelect = 7
    WatchingOther = 8


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

    # if score_v2:
    combo_portion: Optional[float] = None
    bonus_portion: Optional[float] = None


class ReplayFrame(NamedTuple):
    button_state: int
    taiko_byte: int  # pre-taiko support (<=2008)
    x: float
    y: float
    time: int


class ReplayFrameBundle(NamedTuple):
    replay_frames: list[ReplayFrame]
    score_frame: ScoreFrame
    action: ReplayAction
    extra: int
    sequence: int

    raw_data: memoryview  # readonly


@dataclass
class MultiplayerMatch:
    id: int = 0
    in_progress: bool = False

    powerplay: int = 0  # i8
    mods: int = 0  # i32
    name: str = ""
    passwd: str = ""

    map_name: str = ""
    map_id: int = 0  # i32
    map_md5: str = ""

    slot_statuses: list[int] = field(default_factory=list)  # i8
    slot_teams: list[int] = field(default_factory=list)  # i8
    slot_ids: list[int] = field(default_factory=list)  # i8

    host_id: int = 0  # i32

    mode: int = 0  # i8
    win_condition: int = 0  # i8
    team_type: int = 0  # i8

    freemods: bool = False  # i8
    slot_mods: list[int] = field(default_factory=list)  # i32

    seed: int = 0  # i32


class BasePacket(ABC):
    def __init__(self, reader: BanchoPacketReader) -> None:
        ...

    @abstractmethod
    async def handle(self, player: Player) -> None:
        ...


PacketMap = dict[ClientPackets, type[BasePacket]]


class BanchoPacketReader:
    """\
    A class for reading bancho packets
    from the osu! client's request body.

    Attributes
    -----------
    body_view: `memoryview`
        A readonly view of the request's body.

    packet_map: `dict[ClientPackets, BasePacket]`
        The map of registered packets the reader may handle.

    current_length: int
        The length in bytes of the packet currently being handled.

    Intended Usage:
    >>> with memoryview(await request.body()) as body_view:
    ...     for packet in BanchoPacketReader(conn.body):
    ...         await packet.handle()
    """

    def __init__(self, body_view: memoryview, packet_map: PacketMap) -> None:
        self.body_view = body_view  # readonly
        self.packet_map = packet_map

        self.current_len = 0  # last read packet's length

    def __iter__(self) -> Iterator[BasePacket]:
        return self

    def __next__(self) -> BasePacket:
        # do not break until we've read the
        # header of a packet we can handle.
        while self.body_view:  # len(self.view) < 7?
            p_type, p_len = self._read_header()

            if p_type not in self.packet_map:
                # packet type not handled, remove
                # from internal buffer and continue.
                if p_len != 0:
                    self.body_view = self.body_view[p_len:]
            else:
                # we can handle this one.
                break
        else:
            raise StopIteration

        # we have a packet handler for this.
        packet_cls = self.packet_map[p_type]
        self.current_len = p_len

        return packet_cls(self)

    def _read_header(self) -> tuple[ClientPackets, int]:
        """Read the header of an osu! packet (id & length)."""
        # read type & length from the body
        data = struct.unpack("<HxI", self.body_view[:7])
        self.body_view = self.body_view[7:]
        return ClientPackets(data[0]), data[1]

    """ public API (exposed for packet handler's __init__ methods) """

    def read_raw(self) -> memoryview:
        val = self.body_view[: self.current_len]
        self.body_view = self.body_view[self.current_len :]
        return val

    # integral types

    def read_i8(self) -> int:
        val = self.body_view[0]
        self.body_view = self.body_view[1:]
        return val - 256 if val > 127 else val

    def read_u8(self) -> int:
        val = self.body_view[0]
        self.body_view = self.body_view[1:]
        return val

    def read_i16(self) -> int:
        val = int.from_bytes(self.body_view[:2], "little", signed=True)
        self.body_view = self.body_view[2:]
        return val

    def read_u16(self) -> int:
        val = int.from_bytes(self.body_view[:2], "little", signed=False)
        self.body_view = self.body_view[2:]
        return val

    def read_i32(self) -> int:
        val = int.from_bytes(self.body_view[:4], "little", signed=True)
        self.body_view = self.body_view[4:]
        return val

    def read_u32(self) -> int:
        val = int.from_bytes(self.body_view[:4], "little", signed=False)
        self.body_view = self.body_view[4:]
        return val

    def read_i64(self) -> int:
        val = int.from_bytes(self.body_view[:8], "little", signed=True)
        self.body_view = self.body_view[8:]
        return val

    def read_u64(self) -> int:
        val = int.from_bytes(self.body_view[:8], "little", signed=False)
        self.body_view = self.body_view[8:]
        return val

    # floating-point types

    def read_f16(self) -> float:
        (val,) = struct.unpack_from("<e", self.body_view[:2])
        self.body_view = self.body_view[2:]
        return val

    def read_f32(self) -> float:
        (val,) = struct.unpack_from("<f", self.body_view[:4])
        self.body_view = self.body_view[4:]
        return val

    def read_f64(self) -> float:
        (val,) = struct.unpack_from("<d", self.body_view[:8])
        self.body_view = self.body_view[8:]
        return val

    # complex types

    # XXX: some osu! packets use i16 for
    # array length, while others use i32
    def read_i32_list_i16l(self) -> tuple[int]:
        length = int.from_bytes(self.body_view[:2], "little")
        self.body_view = self.body_view[2:]

        val = struct.unpack(f'<{"I" * length}', self.body_view[: length * 4])
        self.body_view = self.body_view[length * 4 :]
        return val

    def read_i32_list_i32l(self) -> tuple[int]:
        length = int.from_bytes(self.body_view[:4], "little")
        self.body_view = self.body_view[4:]

        val = struct.unpack(f'<{"I" * length}', self.body_view[: length * 4])
        self.body_view = self.body_view[length * 4 :]
        return val

    def read_string(self) -> str:
        exists = self.body_view[0] == 0x0B
        self.body_view = self.body_view[1:]

        if not exists:
            # no string sent.
            return ""

        # non-empty string, decode str length (uleb128)
        length = shift = 0

        while True:
            byte = self.body_view[0]
            self.body_view = self.body_view[1:]

            length |= (byte & 0x7F) << shift
            if (byte & 0x80) == 0:
                break

            shift += 7

        val = self.body_view[:length].tobytes().decode()  # copy
        self.body_view = self.body_view[length:]
        return val

    # custom osu! types

    def read_message(self) -> Message:
        """Read an osu! message from the internal buffer."""
        return Message(
            sender=self.read_string(),
            text=self.read_string(),
            recipient=self.read_string(),
            sender_id=self.read_i32(),
        )

    def read_channel(self) -> Channel:
        """Read an osu! channel from the internal buffer."""
        return Channel(
            name=self.read_string(),
            topic=self.read_string(),
            players=self.read_i32(),
        )

    def read_match(self) -> MultiplayerMatch:
        """Read an osu! match from the internal buffer."""
        match = MultiplayerMatch(
            id=self.read_i16(),
            in_progress=self.read_i8() == 1,
            powerplay=self.read_i8(),
            mods=self.read_i32(),
            name=self.read_string(),
            passwd=self.read_string(),
            map_name=self.read_string(),
            map_id=self.read_i32(),
            map_md5=self.read_string(),
            slot_statuses=[self.read_i8() for _ in range(16)],
            slot_teams=[self.read_i8() for _ in range(16)],
            # ^^ up to slot_ids, as it relies on slot_statuses ^^
        )

        for status in match.slot_statuses:
            if status & 124 != 0:  # slot has a player
                match.slot_ids.append(self.read_i32())

        match.host_id = self.read_i32()
        match.mode = self.read_i8()
        match.win_condition = self.read_i8()
        match.team_type = self.read_i8()
        match.freemods = self.read_i8() == 1

        if match.freemods:
            match.slot_mods = [self.read_i32() for _ in range(16)]

        match.seed = self.read_i32()  # used for mania random mod

        return match

    def read_scoreframe(self) -> ScoreFrame:
        sf = ScoreFrame(*SCOREFRAME_FMT.unpack_from(self.body_view[:29]))
        self.body_view = self.body_view[29:]

        if sf.score_v2:
            sf.combo_portion = self.read_f64()
            sf.bonus_portion = self.read_f64()

        return sf

    def read_replayframe(self) -> ReplayFrame:
        return ReplayFrame(
            button_state=self.read_u8(),
            taiko_byte=self.read_u8(),  # pre-taiko support (<=2008)
            x=self.read_f32(),
            y=self.read_f32(),
            time=self.read_i32(),
        )

    def read_replayframe_bundle(self) -> ReplayFrameBundle:
        # save raw format to distribute to the other clients
        raw_data = self.body_view[: self.current_len]

        extra = self.read_i32()  # bancho proto >= 18
        framecount = self.read_u16()
        frames = [self.read_replayframe() for _ in range(framecount)]
        action = ReplayAction(self.read_u8())
        scoreframe = self.read_scoreframe()
        sequence = self.read_u16()

        return ReplayFrameBundle(frames, scoreframe, action, extra, sequence, raw_data)


# write functions


def write_uleb128(num: int) -> Union[bytes, bytearray]:
    """Write `num` into an unsigned LEB128."""
    if num == 0:
        return b"\x00"

    ret = bytearray()

    while num != 0:
        ret.append(num & 0x7F)
        num >>= 7
        if num != 0:
            ret[-1] |= 0x80

    return ret


def write_string(s: str) -> bytes:
    """Write `s` into bytes (ULEB128 & string)."""
    if s:
        encoded = s.encode()
        ret = b"\x0b" + write_uleb128(len(encoded)) + encoded
    else:
        ret = b"\x00"

    return ret


def write_i32_list(l: Collection[int]) -> bytearray:
    """Write `l` into bytes (int32 list)."""
    ret = bytearray(len(l).to_bytes(2, "little"))

    for i in l:
        ret += i.to_bytes(4, "little", signed=True)

    return ret


def write_message(sender: str, msg: str, recipient: str, sender_id: int) -> bytearray:
    """Write params into bytes (osu! message)."""
    ret = bytearray(write_string(sender))
    ret += write_string(msg)
    ret += write_string(recipient)
    ret += sender_id.to_bytes(4, "little", signed=True)
    return ret


def write_channel(name: str, topic: str, count: int) -> bytearray:
    """Write params into bytes (osu! channel)."""
    ret = bytearray(write_string(name))
    ret += write_string(topic)
    ret += count.to_bytes(2, "little")
    return ret


# XXX: deprecated
# def write_mapInfoReply(maps: Sequence[BeatmapInfo]) -> bytearray:
#    """ Write `maps` into bytes (osu! map info). """
#    ret = bytearray(len(maps).to_bytes(4, 'little'))
#
#    # Write files
#    for map in maps:
#        ret += struct.pack('<hiiiBbbbb',
#            map.id, map.map_id, map.set_id, map.thread_id, map.status,
#            map.osu_rank, map.fruits_rank, map.taiko_rank, map.mania_rank
#        )
#        ret += write_string(map.map_md5)
#
#    return ret


def write_match(m: Match, send_pw: bool = True) -> bytearray:
    """Write `m` into bytes (osu! match)."""
    # 0 is for match type
    ret = bytearray(struct.pack("<HbbI", m.id, m.in_progress, 0, m.mods))
    ret += write_string(m.name)

    # osu expects \x0b\x00 if there's a password, but it's
    # not being sent, and \x00 if there's no password.
    if m.passwd:
        if send_pw:
            ret += write_string(m.passwd)
        else:
            ret += b"\x0b\x00"
    else:
        ret += b"\x00"

    ret += write_string(m.map_name)
    ret += m.map_id.to_bytes(4, "little", signed=True)
    ret += write_string(m.map_md5)

    ret.extend([s.status for s in m.slots])
    ret.extend([s.team for s in m.slots])

    for s in m.slots:
        if s.status & 0b01111100 != 0:  # SlotStatus.has_player
            ret += s.player.id.to_bytes(4, "little")

    ret += m.host.id.to_bytes(4, "little")
    ret.extend((m.mode, m.win_condition, m.team_type, m.freemods))

    if m.freemods:
        for s in m.slots:
            ret += s.mods.to_bytes(4, "little")

    ret += m.seed.to_bytes(4, "little")
    return ret


SCOREFRAME_FMT = struct.Struct("<iBHHHHHHiHH?BB?")


def write_scoreframe(s: ScoreFrame) -> bytes:
    """Write `s` into bytes (osu! scoreframe)."""
    return SCOREFRAME_FMT.pack(
        s.time,
        s.id,
        s.num300,
        s.num100,
        s.num50,
        s.num_geki,
        s.num_katu,
        s.num_miss,
        s.total_score,
        s.current_combo,
        s.max_combo,
        s.perfect,
        s.current_hp,
        s.tag_byte,
        s.score_v2,
    )


_noexpand_types: dict[osuTypes, Callable[..., bytes]] = {
    # base
    osuTypes.i8: struct.Struct("<b").pack,
    osuTypes.u8: struct.Struct("<B").pack,
    osuTypes.i16: struct.Struct("<h").pack,
    osuTypes.u16: struct.Struct("<H").pack,
    osuTypes.i32: struct.Struct("<i").pack,
    osuTypes.u32: struct.Struct("<I").pack,
    # osuTypes.f16: struct.Struct('<e').pack, # futureproofing
    osuTypes.f32: struct.Struct("<f").pack,
    osuTypes.i64: struct.Struct("<q").pack,
    osuTypes.u64: struct.Struct("<Q").pack,
    osuTypes.f64: struct.Struct("<d").pack,
    # more complex
    osuTypes.string: write_string,
    osuTypes.i32_list: write_i32_list,
    osuTypes.scoreframe: write_scoreframe,
    # TODO: write replayframe & bundle
}

_expand_types: dict[osuTypes, Callable[..., bytearray]] = {
    # multiarg, tuple expansion
    osuTypes.message: write_message,
    osuTypes.channel: write_channel,
    osuTypes.match: write_match,
}


def write(packid: int, *args: tuple[Any, osuTypes]) -> bytes:
    """Write `args` into bytes."""
    ret = bytearray(struct.pack("<Hx", packid))

    for p_args, p_type in args:
        if p_type == osuTypes.raw:
            ret += p_args
        elif p_type in _noexpand_types:
            ret += _noexpand_types[p_type](p_args)
        elif p_type in _expand_types:
            ret += _expand_types[p_type](*p_args)

    # add size
    ret[3:3] = struct.pack("<I", len(ret) - 3)
    return bytes(ret)


#
# packets
#

# TODO: fix consistency of parameter names


# packet id: 5
@cache
def user_id(user_id: int) -> bytes:
    # id responses:
    # -1: authentication failed
    # -2: old client
    # -3: banned
    # -4: banned
    # -5: error occurred
    # -6: needs supporter
    # -7: password reset
    # -8: requires verification
    # ??: valid id
    return write(ServerPackets.USER_ID, (user_id, osuTypes.i32))


# packet id: 7
def send_message(sender: str, msg: str, recipient: str, sender_id: int) -> bytes:
    return write(
        ServerPackets.SEND_MESSAGE,
        ((sender, msg, recipient, sender_id), osuTypes.message),
    )


# packet id: 8
@cache
def pong() -> bytes:
    return write(ServerPackets.PONG)


# packet id: 9
# NOTE: deprecated
def change_username(old: str, new: str) -> bytes:
    return write(
        ServerPackets.HANDLE_IRC_CHANGE_USERNAME,
        (f"{old}>>>>{new}", osuTypes.string),
    )


BOT_STATUSES = (
    (3, "the source code.."),  # editing
    (6, "geohot livestreams.."),  # watching
    (6, "asottile tutorials.."),  # watching
    (6, "over the server.."),  # watching
    (8, "out new features.."),  # testing
    (9, "a pull request.."),  # submitting
)

# since the bot is always online and is
# also automatically added to all player's
# friends list, their stats are requested
# *very* frequently, and should be cached.
# NOTE: this is cleared once in a while by
# `bg_loops.reroll_bot_status` to keep fresh.


@cache
def bot_stats(player: Player) -> bytes:
    # pick at random from list of potential statuses.
    status_id, status_txt = random.choice(BOT_STATUSES)

    return write(
        ServerPackets.USER_STATS,
        (player.id, osuTypes.i32),  # id
        (status_id, osuTypes.u8),  # action
        (status_txt, osuTypes.string),  # info_text
        ("", osuTypes.string),  # map_md5
        (0, osuTypes.i32),  # mods
        (0, osuTypes.u8),  # mode
        (0, osuTypes.i32),  # map_id
        (0, osuTypes.i64),  # rscore
        (0.0, osuTypes.f32),  # acc
        (0, osuTypes.i32),  # plays
        (0, osuTypes.i64),  # tscore
        (0, osuTypes.i32),  # rank
        (0, osuTypes.i16),  # pp
    )


# packet id: 11
def _user_stats(
    user_id: int,
    action: int,
    info_text: str,
    map_md5: str,
    mods: int,
    mode: int,
    map_id: int,
    ranked_score: int,
    accuracy: float,
    plays: int,
    total_score: int,
    global_rank: int,
    pp: int,
) -> bytes:
    if pp > 0x7FFF:
        # HACK: if pp is over osu!'s ingame cap,
        # we can instead display it as ranked score
        ranked_score = pp
        pp = 0

    return write(
        ServerPackets.USER_STATS,
        (user_id, osuTypes.i32),
        (action, osuTypes.u8),
        (info_text, osuTypes.string),
        (map_md5, osuTypes.string),
        (mods, osuTypes.i32),
        (mode, osuTypes.u8),
        (map_id, osuTypes.i32),
        (ranked_score, osuTypes.i64),
        (accuracy / 100.0, osuTypes.f32),
        (plays, osuTypes.i32),
        (total_score, osuTypes.i64),
        (global_rank, osuTypes.i32),
        (pp, osuTypes.i16),  # why not u16 peppy :(
    )


# TODO: this is implementation-specific, move it out
def user_stats(player: Player) -> bytes:
    gm_stats = player.gm_stats
    if gm_stats.pp > 0x7FFF:
        # HACK: if pp is over osu!'s ingame cap,
        # we can instead display it as ranked score
        rscore = gm_stats.pp
        pp = 0
    else:
        rscore = gm_stats.rscore
        pp = gm_stats.pp

    return write(
        ServerPackets.USER_STATS,
        (player.id, osuTypes.i32),
        (player.status.action, osuTypes.u8),
        (player.status.info_text, osuTypes.string),
        (player.status.map_md5, osuTypes.string),
        (player.status.mods, osuTypes.i32),
        (player.status.mode.as_vanilla, osuTypes.u8),
        (player.status.map_id, osuTypes.i32),
        (rscore, osuTypes.i64),
        (gm_stats.acc / 100.0, osuTypes.f32),
        (gm_stats.plays, osuTypes.i32),
        (gm_stats.tscore, osuTypes.i64),
        (gm_stats.rank, osuTypes.i32),
        (pp, osuTypes.i16),  # why not u16 peppy :(
    )


# packet id: 12
@cache
def logout(user_id: int) -> bytes:
    return write(ServerPackets.USER_LOGOUT, (user_id, osuTypes.i32), (0, osuTypes.u8))


# packet id: 13
@cache
def spectator_joined(user_id: int) -> bytes:
    return write(ServerPackets.SPECTATOR_JOINED, (user_id, osuTypes.i32))


# packet id: 14
@cache
def spectator_left(user_id: int) -> bytes:
    return write(ServerPackets.SPECTATOR_LEFT, (user_id, osuTypes.i32))


# packet id: 15
def spectate_frames(data: bytes) -> bytes:
    # NOTE: this is left as unvalidated (raw) for efficiency due to the
    # sheer rate of usage of these packets in spectator mode.

    # spectator frames *received* by the server are always validated.

    return write(ServerPackets.SPECTATE_FRAMES, (data, osuTypes.raw))


# packet id: 19
@cache
def version_update() -> bytes:
    return write(ServerPackets.VERSION_UPDATE)


# packet id: 22
@cache
def spectator_cant_spectate(user_id: int) -> bytes:
    return write(ServerPackets.SPECTATOR_CANT_SPECTATE, (user_id, osuTypes.i32))


# packet id: 23
@cache
def get_attention() -> bytes:
    return write(ServerPackets.GET_ATTENTION)


# packet id: 24
@lru_cache(maxsize=4)
def notification(msg: str) -> bytes:
    return write(ServerPackets.NOTIFICATION, (msg, osuTypes.string))


# packet id: 26
def update_match(m: Match, send_pw: bool = True) -> bytes:
    return write(ServerPackets.UPDATE_MATCH, ((m, send_pw), osuTypes.match))


# packet id: 27
def new_match(m: Match) -> bytes:
    return write(ServerPackets.NEW_MATCH, ((m, True), osuTypes.match))


# packet id: 28
@cache
def dispose_match(id: int) -> bytes:
    return write(ServerPackets.DISPOSE_MATCH, (id, osuTypes.i32))


# packet id: 34
@cache
def toggle_block_non_friend_dm() -> bytes:
    return write(ServerPackets.TOGGLE_BLOCK_NON_FRIEND_DMS)


# packet id: 36
def match_join_success(m: Match) -> bytes:
    return write(ServerPackets.MATCH_JOIN_SUCCESS, ((m, True), osuTypes.match))


# packet id: 37
@cache
def match_join_fail() -> bytes:
    return write(ServerPackets.MATCH_JOIN_FAIL)


# packet id: 42
@cache
def fellow_spectator_joined(user_id: int) -> bytes:
    return write(ServerPackets.FELLOW_SPECTATOR_JOINED, (user_id, osuTypes.i32))


# packet id: 43
@cache
def fellow_spectator_left(user_id: int) -> bytes:
    return write(ServerPackets.FELLOW_SPECTATOR_LEFT, (user_id, osuTypes.i32))


# packet id: 46
def match_start(m: Match) -> bytes:
    return write(ServerPackets.MATCH_START, ((m, True), osuTypes.match))


# packet id: 48
# NOTE: this is actually unused, since it's
#       much faster to just send the bytes back
#       rather than parsing them. Though I might
#       end up doing it eventually for security reasons
def match_score_update(frame: ScoreFrame) -> bytes:
    return write(ServerPackets.MATCH_SCORE_UPDATE, (frame, osuTypes.scoreframe))


# packet id: 50
@cache
def match_transfer_host() -> bytes:
    return write(ServerPackets.MATCH_TRANSFER_HOST)


# packet id: 53
@cache
def match_all_players_loaded() -> bytes:
    return write(ServerPackets.MATCH_ALL_PLAYERS_LOADED)


# packet id: 57
@cache
def match_player_failed(slot_id: int) -> bytes:
    return write(ServerPackets.MATCH_PLAYER_FAILED, (slot_id, osuTypes.i32))


# packet id: 58
@cache
def match_complete() -> bytes:
    return write(ServerPackets.MATCH_COMPLETE)


# packet id: 61
@cache
def match_skip() -> bytes:
    return write(ServerPackets.MATCH_SKIP)


# packet id: 64
@lru_cache(maxsize=16)
def channel_join(name: str) -> bytes:
    return write(ServerPackets.CHANNEL_JOIN_SUCCESS, (name, osuTypes.string))


# packet id: 65
@lru_cache(maxsize=8)
def channel_info(name: str, topic: str, p_count: int) -> bytes:
    return write(ServerPackets.CHANNEL_INFO, ((name, topic, p_count), osuTypes.channel))


# packet id: 66
@lru_cache(maxsize=8)
def channel_kick(name: str) -> bytes:
    return write(ServerPackets.CHANNEL_KICK, (name, osuTypes.string))


# packet id: 67
@lru_cache(maxsize=8)
def channel_auto_join(name: str, topic: str, p_count: int) -> bytes:
    return write(
        ServerPackets.CHANNEL_AUTO_JOIN,
        ((name, topic, p_count), osuTypes.channel),
    )


# packet id: 69
# def beatmap_info_reply(maps: Sequence[BeatmapInfo]) -> bytes:
#    return write(
#        Packets.CHO_BEATMAP_INFO_REPLY,
#        (maps, osuTypes.mapInfoReply)
#    )


# packet id: 71
@cache
def bancho_privileges(priv: int) -> bytes:
    return write(ServerPackets.PRIVILEGES, (priv, osuTypes.i32))


# packet id: 72
def friends_list(friends: Collection[int]) -> bytes:
    return write(ServerPackets.FRIENDS_LIST, (friends, osuTypes.i32_list))


# packet id: 75
@cache
def protocol_version(ver: int) -> bytes:
    return write(ServerPackets.PROTOCOL_VERSION, (ver, osuTypes.i32))


# packet id: 76
@cache
def main_menu_icon(icon_url: str, onclick_url: str) -> bytes:
    return write(
        ServerPackets.MAIN_MENU_ICON,
        (icon_url + "|" + onclick_url, osuTypes.string),
    )


# packet id: 80
# NOTE: deprecated
@cache
def monitor() -> bytes:
    # this is an older (now removed) 'anticheat' feature of the osu!
    # client; basically, it would do some checks (most likely for aqn),
    # screenshot your desktop (and send it to osu! servers), then trigger
    # the processlist to be sent to bancho as well (also now unused).

    # this doesn't work on newer clients, and I had no plans
    # of trying to put it to use - just coded for completion.
    return write(ServerPackets.MONITOR)


# packet id: 81
@cache
def match_player_skipped(user_id: int) -> bytes:
    return write(ServerPackets.MATCH_PLAYER_SKIPPED, (user_id, osuTypes.i32))


# since the bot is always online and is
# also automatically added to all player's
# friends list, their presence is requested
# *very* frequently; only build it once.
@cache
def bot_presence(player: Player) -> bytes:
    return write(
        ServerPackets.USER_PRESENCE,
        (player.id, osuTypes.i32),
        (player.name, osuTypes.string),
        (-5 + 24, osuTypes.u8),
        (245, osuTypes.u8),  # satellite provider
        (31, osuTypes.u8),
        (1234.0, osuTypes.f32),  # send coordinates waaay
        (4321.0, osuTypes.f32),  # off the map for the bot
        (0, osuTypes.i32),
    )


# packet id: 83
def _user_presence(
    user_id: int,
    name: str,
    utc_offset: int,
    country_code: int,
    bancho_privileges: int,
    mode: int,
    latitude: int,
    longitude: int,
    global_rank: int,
) -> bytes:
    return write(
        ServerPackets.USER_PRESENCE,
        (user_id, osuTypes.i32),
        (name, osuTypes.string),
        (utc_offset + 24, osuTypes.u8),
        (country_code, osuTypes.u8),
        (bancho_privileges | (mode << 5), osuTypes.u8),
        (longitude, osuTypes.f32),
        (latitude, osuTypes.f32),
        (global_rank, osuTypes.i32),
    )


# TODO: this is implementation-specific, move it out
def user_presence(player: Player) -> bytes:
    return write(
        ServerPackets.USER_PRESENCE,
        (player.id, osuTypes.i32),
        (player.name, osuTypes.string),
        (player.utc_offset + 24, osuTypes.u8),
        (player.geoloc["country"]["numeric"], osuTypes.u8),
        (player.bancho_priv | (player.status.mode.as_vanilla << 5), osuTypes.u8),
        (player.geoloc["longitude"], osuTypes.f32),
        (player.geoloc["latitude"], osuTypes.f32),
        (player.gm_stats.rank, osuTypes.i32),
    )


# packet id: 86
@cache
def restart_server(ms: int) -> bytes:
    return write(ServerPackets.RESTART, (ms, osuTypes.i32))


# packet id: 88
def match_invite(player: Player, target_name: str) -> bytes:
    msg = f"Come join my game: {player.match.embed}."
    return write(
        ServerPackets.MATCH_INVITE,
        ((player.name, msg, target_name, player.id), osuTypes.message),
    )


# packet id: 89
@cache
def channel_info_end() -> bytes:
    return write(ServerPackets.CHANNEL_INFO_END)


# packet id: 91
def match_change_password(new: str) -> bytes:
    return write(ServerPackets.MATCH_CHANGE_PASSWORD, (new, osuTypes.string))


# packet id: 92
def silence_end(delta: int) -> bytes:
    return write(ServerPackets.SILENCE_END, (delta, osuTypes.i32))


# packet id: 94
@cache
def user_silenced(user_id: int) -> bytes:
    return write(ServerPackets.USER_SILENCED, (user_id, osuTypes.i32))


""" not sure why 95 & 96 exist? unused in bancho.py """


# packet id: 95
@cache
def user_presence_single(user_id: int) -> bytes:
    return write(ServerPackets.USER_PRESENCE_SINGLE, (user_id, osuTypes.i32))


# packet id: 96
def user_presence_bundle(user_ids: Collection[int]) -> bytes:
    return write(ServerPackets.USER_PRESENCE_BUNDLE, (user_ids, osuTypes.i32_list))


# packet id: 100
def user_dm_blocked(target: str) -> bytes:
    return write(ServerPackets.USER_DM_BLOCKED, (("", "", target, 0), osuTypes.message))


# packet id: 101
def target_silenced(target: str) -> bytes:
    return write(
        ServerPackets.TARGET_IS_SILENCED,
        (("", "", target, 0), osuTypes.message),
    )


# packet id: 102
@cache
def version_update_forced() -> bytes:
    return write(ServerPackets.VERSION_UPDATE_FORCED)


# packet id: 103
def switch_server(t: int) -> bytes:
    # increment endpoint index if
    # idletime >= t && match == null
    return write(ServerPackets.SWITCH_SERVER, (t, osuTypes.i32))


# packet id: 104
@cache
def account_restricted() -> bytes:
    return write(ServerPackets.ACCOUNT_RESTRICTED)


# packet id: 105
# NOTE: deprecated
def rtx(msg: str) -> bytes:
    # a bit of a weird one, sends a request to the client
    # to show some visual effects on screen for 5 seconds:
    # - black screen, freezes game, beeps loudly.
    # within the next 3-8 seconds at random.
    return write(ServerPackets.RTX, (msg, osuTypes.string))


# packet id: 106
@cache
def match_abort() -> bytes:
    return write(ServerPackets.MATCH_ABORT)


# packet id: 107
def switch_tournament_server(ip: str) -> bytes:
    # the client only reads the string if it's
    # not on the client's normal endpoints,
    # but we can send it either way xd.
    return write(ServerPackets.SWITCH_TOURNAMENT_SERVER, (ip, osuTypes.string))
