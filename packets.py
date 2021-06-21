# -*- coding: utf-8 -*-

# NOTE: at some point, parts (or all) of this may
# be rewritten in cython (or c++ ported with cython)?
# i'm not sure how well it works with an async setup
# like this, but we'll see B) massive speed gains tho

import struct
import random
from abc import ABC
from enum import IntEnum
from enum import unique
from functools import cache
from functools import lru_cache
from typing import Iterator
from typing import NamedTuple
from typing import Sequence
from typing import TYPE_CHECKING
from typing import Union

from constants.gamemodes import GameMode
from constants.mods import Mods
from constants.types import osuTypes
from objects import glob
#from objects.beatmap import BeatmapInfo
from objects.match import Match
from objects.match import MatchTeams
from objects.match import MatchTeamTypes
from objects.match import MatchWinConditions
from objects.match import ScoreFrame
from objects.match import SlotStatus
from utils.misc import escape_enum
from utils.misc import pymysql_encode

if TYPE_CHECKING:
    from objects.player import Player

# tuple of some of struct's format specifiers
# for clean access within packet pack/unpack.

@unique
@pymysql_encode(escape_enum)
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
        return f'<{self.name} ({self.value})>'

@unique
@pymysql_encode(escape_enum)
class ServerPackets(IntEnum):
    USER_ID = 5
    SEND_MESSAGE = 7
    PONG = 8
    HANDLE_IRC_CHANGE_USERNAME = 9 # unused
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
    UNAUTHORIZED = 62 # unused
    CHANNEL_JOIN_SUCCESS = 64
    CHANNEL_INFO = 65
    CHANNEL_KICK = 66
    CHANNEL_AUTO_JOIN = 67
    BEATMAP_INFO_REPLY = 69
    PRIVILEGES = 71
    FRIENDS_LIST = 72
    PROTOCOL_VERSION = 75
    MAIN_MENU_ICON = 76
    MONITOR = 80 # unused
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
    RTX = 105 # unused
    MATCH_ABORT = 106
    SWITCH_TOURNAMENT_SERVER = 107

    def __repr__(self) -> str:
        return f'<{self.name} ({self.value})>'

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

class ReplayFrame(NamedTuple):
    button_state: int
    taiko_byte: int # pre-taiko support (<=2008)
    x: float
    y: float
    time: int

class ReplayFrameBundle(NamedTuple):
    replay_frames: list[ReplayFrame]
    score_frame: ScoreFrame
    action: ReplayAction
    extra: int
    sequence: int

    raw_data: memoryview # readonly

class BasePacket(ABC):
    def __init__(self, reader: 'BanchoPacketReader') -> None: ...
    async def handle(self, p: 'Player') -> None: ...

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
    ```
      for packet in BanchoPacketReader(conn.body):
          # once you're ready to handle the packet,
          # simply call it's .handle() method.
          await packet.handle()
    ```
    """
    __slots__ = ('body_view', 'packet_map', 'current_len')

    def __init__(self, body_view: memoryview, packet_map: dict) -> None:
        self.body_view = body_view # readonly
        self.packet_map = packet_map

        self.current_len = 0 # last read packet's length

    def __iter__(self) -> Iterator[BasePacket]:
        return self

    def __next__(self):
        # do not break until we've read the
        # header of a packet we can handle.
        while self.body_view: # len(self.view) < 7?
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

    def _read_header(self) -> tuple[int, int]:
        """Read the header of an osu! packet (id & length)."""
        # read type & length from the body
        data = struct.unpack('<HxI', self.body_view[:7])
        self.body_view = self.body_view[7:]
        return ClientPackets(data[0]), data[1]

    """ public API (exposed for packet handler's __init__ methods) """

    def read_raw(self) -> memoryview:
        val = self.body_view[:self.current_len]
        self.body_view = self.body_view[self.current_len:]
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
        val = int.from_bytes(self.body_view[:2], 'little', signed=True)
        self.body_view = self.body_view[2:]
        return val

    def read_u16(self) -> int:
        val = int.from_bytes(self.body_view[:2], 'little', signed=False)
        self.body_view = self.body_view[2:]
        return val

    def read_i32(self) -> int:
        val = int.from_bytes(self.body_view[:4], 'little', signed=True)
        self.body_view = self.body_view[4:]
        return val

    def read_u32(self) -> int:
        val = int.from_bytes(self.body_view[:4], 'little', signed=False)
        self.body_view = self.body_view[4:]
        return val

    def read_i64(self) -> int:
        val = int.from_bytes(self.body_view[:8], 'little', signed=True)
        self.body_view = self.body_view[8:]
        return val

    def read_u64(self) -> int:
        val = int.from_bytes(self.body_view[:8], 'little', signed=False)
        self.body_view = self.body_view[8:]
        return val

    # floating-point types

    def read_f16(self) -> float:
        val, = struct.unpack_from('<e', self.body_view[:2])
        self.body_view = self.body_view[2:]
        return val

    def read_f32(self) -> float:
        val, = struct.unpack_from('<f', self.body_view[:4])
        self.body_view = self.body_view[4:]
        return val

    def read_f64(self) -> float:
        val, = struct.unpack_from('<d', self.body_view[:8])
        self.body_view = self.body_view[8:]
        return val

    # complex types

    # XXX: some osu! packets use i16 for
    # array length, while others use i32
    def read_i32_list_i16l(self) -> tuple[int]:
        length = int.from_bytes(self.body_view[:2], 'little')
        self.body_view = self.body_view[2:]

        val = struct.unpack(f'<{"I" * length}', self.body_view[:length * 4])
        self.body_view = self.body_view[length * 4:]
        return val

    def read_i32_list_i32l(self) -> tuple[int]:
        length = int.from_bytes(self.body_view[:4], 'little')
        self.body_view = self.body_view[4:]

        val = struct.unpack(f'<{"I" * length}', self.body_view[:length * 4])
        self.body_view = self.body_view[length * 4:]
        return val

    def read_string(self) -> str:
        exists = self.body_view[0] == 0x0b
        self.body_view = self.body_view[1:]

        if not exists:
            # no string sent.
            return ''

        # non-empty string, decode str length (uleb128)
        length = shift = 0

        while True:
            b = self.body_view[0]
            self.body_view = self.body_view[1:]

            length |= (b & 0b01111111) << shift
            if (b & 0b10000000) == 0:
                break

            shift += 7

        val = self.body_view[:length].tobytes().decode() # copy
        self.body_view = self.body_view[length:]
        return val

    # custom osu! types

    def read_message(self) -> Message:
        """Read an osu! message from the internal buffer."""
        return Message(
            sender=self.read_string(),
            text=self.read_string(),
            recipient=self.read_string(),
            sender_id=self.read_i32()
        )

    def read_channel(self) -> Channel:
        """Read an osu! channel from the internal buffer."""
        return Channel(
            name=self.read_string(),
            topic=self.read_string(),
            players=self.read_i32()
        )

    def read_match(self) -> Match:
        """Read an osu! match from the internal buffer."""
        m = Match()

        # ignore match id (i16) and inprogress (i8).
        self.body_view = self.body_view[3:]

        self.read_i8() # powerplay unused

        m.mods = Mods(self.read_i32())

        m.name = self.read_string()
        m.passwd = self.read_string()

        m.map_name = self.read_string()
        m.map_id = self.read_i32()
        m.map_md5 = self.read_string()

        for slot in m.slots:
            slot.status = SlotStatus(self.read_i8())

        for slot in m.slots:
            slot.team = MatchTeams(self.read_i8())

        for slot in m.slots:
            if slot.status & SlotStatus.has_player:
                # we don't need this, ignore it.
                self.body_view = self.body_view[4:]

        host_id = self.read_i32()
        m.host = glob.players.get(id=host_id)

        m.mode = GameMode(self.read_i8())
        m.win_condition = MatchWinConditions(self.read_i8())
        m.team_type = MatchTeamTypes(self.read_i8())
        m.freemods = self.read_i8() == 1

        # if we're in freemods mode,
        # read individual slot mods.
        if m.freemods:
            for slot in m.slots:
                slot.mods = Mods(self.read_i32())

        # read the seed (used for mania)
        m.seed = self.read_i32()

        return m

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
            taiko_byte=self.read_u8(), # pre-taiko support (<=2008)
            x=self.read_f32(),
            y=self.read_f32(),
            time=self.read_i32()
        )

    def read_replayframe_bundle(self) -> ReplayFrameBundle:
        # save raw format to distribute to the other clients
        raw_data = self.body_view[:self.current_len]

        extra = self.read_i32() # bancho proto >= 18
        framecount = self.read_u16()
        frames = [self.read_replayframe() for _ in range(framecount)]
        action = ReplayAction(self.read_u8())
        scoreframe = self.read_scoreframe()
        sequence = self.read_u16()

        return ReplayFrameBundle(
            frames, scoreframe, action,
            extra, sequence, raw_data
        )

# write functions

def write_uleb128(num: int) -> Union[bytes, bytearray]:
    """ Write `num` into an unsigned LEB128. """
    if num == 0:
        return b'\x00'

    ret = bytearray()
    length = 0

    while num > 0:
        ret.append(num & 0b01111111)
        num >>= 7
        if num != 0:
            ret[length] |= 0b10000000
        length += 1

    return ret

def write_string(s: str) -> Union[bytes, bytearray]:
    """ Write `s` into bytes (ULEB128 & string). """
    if s:
        encoded = s.encode()
        ret = bytearray(b'\x0b')
        ret += write_uleb128(len(encoded))
        ret += encoded
    else:
        ret = b'\x00'

    return ret

def write_i32_list(l: Sequence[int]) -> bytearray:
    """ Write `l` into bytes (int32 list). """
    ret = bytearray(len(l).to_bytes(2, 'little'))

    for i in l:
        ret += i.to_bytes(4, 'little')

    return ret

def write_message(sender: str, msg: str, recipient: str,
                  sender_id: int) -> bytearray:
    """ Write params into bytes (osu! message). """
    ret = bytearray(write_string(sender))
    ret += write_string(msg)
    ret += write_string(recipient)
    ret += sender_id.to_bytes(4, 'little', signed=True)
    return ret

def write_channel(name: str, topic: str,
                  count: int) -> bytearray:
    """ Write params into bytes (osu! channel). """
    ret = bytearray(write_string(name))
    ret += write_string(topic)
    ret += count.to_bytes(2, 'little')
    return ret

# XXX: deprecated
#def write_mapInfoReply(maps: Sequence[BeatmapInfo]) -> bytearray:
#    """ Write `maps` into bytes (osu! map info). """
#    ret = bytearray(len(maps).to_bytes(4, 'little'))
#
#    # Write files
#    for m in maps:
#        ret += struct.pack('<hiiiBbbbb',
#            m.id, m.map_id, m.set_id, m.thread_id, m.status,
#            m.osu_rank, m.fruits_rank, m.taiko_rank, m.mania_rank
#        )
#        ret += write_string(m.map_md5)
#
#    return ret

def write_match(m: Match, send_pw: bool = True) -> bytearray:
    """ Write `m` into bytes (osu! match). """
    # 0 is for match type
    ret = bytearray(struct.pack('<HbbI', m.id, m.in_progress, 0, m.mods))
    ret += write_string(m.name)

    # osu expects \x0b\x00 if there's a password but it's
    # not being sent, and \x00 if there's no password.
    if m.passwd:
        if send_pw:
            ret += write_string(m.passwd)
        else:
            ret += b'\x0b\x00'
    else:
        ret += b'\x00'

    ret += write_string(m.map_name)
    ret += m.map_id.to_bytes(4, 'little', signed=True)
    ret += write_string(m.map_md5)

    ret.extend([s.status for s in m.slots])
    ret.extend([s.team for s in m.slots])

    for s in m.slots:
        if s.status & SlotStatus.has_player:
            ret += s.player.id.to_bytes(4, 'little')

    ret += m.host.id.to_bytes(4, 'little')
    ret.extend((m.mode, m.win_condition,
                m.team_type, m.freemods))

    if m.freemods:
        for s in m.slots:
            ret += s.mods.to_bytes(4, 'little')

    ret += m.seed.to_bytes(4, 'little')
    return ret

SCOREFRAME_FMT = struct.Struct('<iBHHHHHHiHH?BB?')
def write_scoreframe(s: ScoreFrame) -> bytes:
    """ Write `s` into bytes (osu! scoreframe). """
    return SCOREFRAME_FMT.pack(
        s.time, s.id, s.num300, s.num100, s.num50, s.num_geki,
        s.num_katu, s.num_miss, s.total_score, s.current_combo,
        s.max_combo, s.perfect, s.current_hp, s.tag_byte, s.score_v2
    )

_noexpand_types = {
    # base
    osuTypes.i8:  struct.Struct('<b').pack,
    osuTypes.u8:  struct.Struct('<B').pack,
    osuTypes.i16: struct.Struct('<h').pack,
    osuTypes.u16: struct.Struct('<H').pack,
    osuTypes.i32: struct.Struct('<i').pack,
    osuTypes.u32: struct.Struct('<I').pack,
    #osuTypes.f16: struct.Struct('<e').pack, # futureproofing
    osuTypes.f32: struct.Struct('<f').pack,
    osuTypes.i64: struct.Struct('<q').pack,
    osuTypes.u64: struct.Struct('<Q').pack,
    osuTypes.f64: struct.Struct('<d').pack,

    # more complex
    osuTypes.string: write_string,
    osuTypes.i32_list: write_i32_list,
    osuTypes.scoreframe: write_scoreframe,
    # TODO: write replayframe & bundle?
}

_expand_types = {
    # multiarg, tuple expansion
    osuTypes.message: write_message,
    osuTypes.channel: write_channel,
    osuTypes.match: write_match,
}

def write(packid: int, *args: Sequence[object]) -> bytes:
    """ Write `args` into bytes. """
    ret = bytearray(struct.pack('<Hx', packid))

    for p_args, p_type in args:
        if p_type == osuTypes.raw:
            ret += p_args
        elif p_type in _noexpand_types:
            ret += _noexpand_types[p_type](p_args)
        elif p_type in _expand_types:
            ret += _expand_types[p_type](*p_args)

    # add size
    ret[3:3] = struct.pack('<I', len(ret) - 3)
    return bytes(ret)

#
# packets
#

# packet id: 5
@cache
def userID(id: int) -> bytes:
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
    return write(
        ServerPackets.USER_ID,
        (id, osuTypes.i32)
    )

# packet id: 7
def sendMessage(sender: str, msg: str, recipient: str,
                sender_id: int) -> bytes:
    return write(
        ServerPackets.SEND_MESSAGE,
        ((sender, msg, recipient, sender_id), osuTypes.message)
    )

# packet id: 8
@cache
def pong() -> bytes:
    return write(ServerPackets.PONG)

# packet id: 9
# NOTE: deprecated
def changeUsername(old: str, new: str) -> bytes:
    return write(
        ServerPackets.HANDLE_IRC_CHANGE_USERNAME,
        (f'{old}>>>>{new}', osuTypes.string)
    )

BOT_STATUSES = (
    (3, 'the source code..'), # editing
    (6, 'geohot livestreams..'), # watching
    (6, 'over the server..'), # watching
    (8, 'out new features..'), # testing
    (9, 'a pull request..'), # submitting
)

# since the bot is always online and is
# also automatically added to all player's
# friends list, their stats are requested
# *very* frequently, and should be cached.
# NOTE: this is cleared once in a while by
# `bg_loops.reroll_bot_status` to keep fresh.

@cache
def botStats():
    # pick at random from list of potential statuses.
    status_id, status_txt = random.choice(BOT_STATUSES)

    return write(
        ServerPackets.USER_STATS,
        (glob.bot.id, osuTypes.i32), # id
        (status_id, osuTypes.u8), # action
        (status_txt, osuTypes.string), # info_text
        ('', osuTypes.string), # map_md5
        (0, osuTypes.i32), # mods
        (0, osuTypes.u8), # mode
        (0, osuTypes.i32), # map_id
        (0, osuTypes.i64), # rscore
        (0.0, osuTypes.f32), # acc
        (0, osuTypes.i32), # plays
        (0, osuTypes.i64), # tscore
        (0, osuTypes.i32), # rank
        (0, osuTypes.i16) # pp
    )

# packet id: 11
def userStats(p: 'Player') -> bytes:
    if p is glob.bot:
        return botStats()

    gm_stats = p.gm_stats
    if gm_stats.pp > 0x7fff:
        # over osu! pp cap, we'll have to
        # show their pp as ranked score.
        rscore = gm_stats.pp
        pp = 0
    else:
        rscore = gm_stats.rscore
        pp = gm_stats.pp

    return write(
        ServerPackets.USER_STATS,
        (p.id, osuTypes.i32),
        (p.status.action, osuTypes.u8),
        (p.status.info_text, osuTypes.string),
        (p.status.map_md5, osuTypes.string),
        (p.status.mods, osuTypes.i32),
        (p.status.mode.as_vanilla, osuTypes.u8),
        (p.status.map_id, osuTypes.i32),
        (rscore, osuTypes.i64),
        (gm_stats.acc / 100.0, osuTypes.f32),
        (gm_stats.plays, osuTypes.i32),
        (gm_stats.tscore, osuTypes.i64),
        (gm_stats.rank, osuTypes.i32),
        (pp, osuTypes.i16) # why not u16 peppy :(
    )

# packet id: 12
@cache
def logout(userID: int) -> bytes:
    return write(
        ServerPackets.USER_LOGOUT,
        (userID, osuTypes.i32),
        (0, osuTypes.u8)
    )

# packet id: 13
@cache
def spectatorJoined(id: int) -> bytes:
    return write(
        ServerPackets.SPECTATOR_JOINED,
        (id, osuTypes.i32)
    )

# packet id: 14
@cache
def spectatorLeft(id: int) -> bytes:
    return write(
        ServerPackets.SPECTATOR_LEFT,
        (id, osuTypes.i32)
    )

# packet id: 15
# TODO: perhaps optimize this and match
# frames to be a bit more efficient, since
# they're literally spammed between clients.
def spectateFrames(data: bytes) -> bytes:
    return write(
        ServerPackets.SPECTATE_FRAMES,
        (data, osuTypes.raw)
    )

# packet id: 19
@cache
def versionUpdate() -> bytes:
    return write(ServerPackets.VERSION_UPDATE)

# packet id: 22
@cache
def spectatorCantSpectate(id: int) -> bytes:
    return write(
        ServerPackets.SPECTATOR_CANT_SPECTATE,
        (id, osuTypes.i32)
    )

# packet id: 23
@cache
def getAttention() -> bytes:
    return write(ServerPackets.GET_ATTENTION)

# packet id: 24
@lru_cache(maxsize=4)
def notification(msg: str) -> bytes:
    return write(
        ServerPackets.NOTIFICATION,
        (msg, osuTypes.string)
    )

# packet id: 26
def updateMatch(m: Match, send_pw: bool = True) -> bytes:
    return write(
        ServerPackets.UPDATE_MATCH,
        ((m, send_pw), osuTypes.match)
    )

# packet id: 27
def newMatch(m: Match) -> bytes:
    return write(
        ServerPackets.NEW_MATCH,
        ((m, True), osuTypes.match)
    )

# packet id: 28
@cache
def disposeMatch(id: int) -> bytes:
    return write(
        ServerPackets.DISPOSE_MATCH,
        (id, osuTypes.i32)
    )

# packet id: 34
@cache
def toggleBlockNonFriendPM() -> bytes:
    return write(ServerPackets.TOGGLE_BLOCK_NON_FRIEND_DMS)

# packet id: 36
def matchJoinSuccess(m: Match) -> bytes:
    return write(
        ServerPackets.MATCH_JOIN_SUCCESS,
        ((m, True), osuTypes.match)
    )

# packet id: 37
@cache
def matchJoinFail() -> bytes:
    return write(ServerPackets.MATCH_JOIN_FAIL)

# packet id: 42
@cache
def fellowSpectatorJoined(id: int) -> bytes:
    return write(
        ServerPackets.FELLOW_SPECTATOR_JOINED,
        (id, osuTypes.i32)
    )

# packet id: 43
@cache
def fellowSpectatorLeft(id: int) -> bytes:
    return write(
        ServerPackets.FELLOW_SPECTATOR_LEFT,
        (id, osuTypes.i32)
    )

# packet id: 46
def matchStart(m: Match) -> bytes:
    return write(
        ServerPackets.MATCH_START,
        ((m, True), osuTypes.match)
    )

# packet id: 48
# NOTE: this is actually unused, since it's
#       much faster to just send the bytes back
#       rather than parsing them.. though I might
#       end up doing it eventually for security reasons
def matchScoreUpdate(frame: ScoreFrame) -> bytes:
    return write(
        ServerPackets.MATCH_SCORE_UPDATE,
        (frame, osuTypes.scoreframe)
    )

# packet id: 50
@cache
def matchTransferHost() -> bytes:
    return write(ServerPackets.MATCH_TRANSFER_HOST)

# packet id: 53
@cache
def matchAllPlayerLoaded() -> bytes:
    return write(ServerPackets.MATCH_ALL_PLAYERS_LOADED)

# packet id: 57
@cache
def matchPlayerFailed(slot_id: int) -> bytes:
    return write(
        ServerPackets.MATCH_PLAYER_FAILED,
        (slot_id, osuTypes.i32)
    )

# packet id: 58
@cache
def matchComplete() -> bytes:
    return write(ServerPackets.MATCH_COMPLETE)

# packet id: 61
@cache
def matchSkip() -> bytes:
    return write(ServerPackets.MATCH_SKIP)

# packet id: 64
@lru_cache(maxsize=16)
def channelJoin(name: str) -> bytes:
    return write(
        ServerPackets.CHANNEL_JOIN_SUCCESS,
        (name, osuTypes.string)
    )

# packet id: 65
@lru_cache(maxsize=8)
def channelInfo(name: str, topic: str,
                p_count: int) -> bytes:
    return write(
        ServerPackets.CHANNEL_INFO,
        ((name, topic, p_count), osuTypes.channel)
    )

# packet id: 66
@lru_cache(maxsize=8)
def channelKick(name: str) -> bytes:
    return write(
        ServerPackets.CHANNEL_KICK,
        (name, osuTypes.string)
    )

# packet id: 67
@lru_cache(maxsize=8)
def channelAutoJoin(name: str, topic: str,
                    p_count: int) -> bytes:
    return write(
        ServerPackets.CHANNEL_AUTO_JOIN,
        ((name, topic, p_count), osuTypes.channel)
    )

# packet id: 69
#def beatmapInfoReply(maps: Sequence[BeatmapInfo]) -> bytes:
#    return write(
#        Packets.CHO_BEATMAP_INFO_REPLY,
#        (maps, osuTypes.mapInfoReply)
#    )

# packet id: 71
@cache
def banchoPrivileges(priv: int) -> bytes:
    return write(
        ServerPackets.PRIVILEGES,
        (priv, osuTypes.i32)
    )

# packet id: 72
def friendsList(*friends) -> bytes:
    return write(
        ServerPackets.FRIENDS_LIST,
        (friends, osuTypes.i32_list)
    )

# packet id: 75
@cache
def protocolVersion(ver: int) -> bytes:
    return write(
        ServerPackets.PROTOCOL_VERSION,
        (ver, osuTypes.i32)
    )

# packet id: 76
@cache
def mainMenuIcon() -> bytes:
    return write(
        ServerPackets.MAIN_MENU_ICON,
        ('|'.join(glob.config.menu_icon), osuTypes.string)
    )

# packet id: 80
# NOTE: deprecated
@cache
def monitor() -> bytes:
    # this is an older (now removed) 'anticheat' feature of the osu!
    # client; basically, it would do some checks (most likely for aqn),
    # screenshot your desktop (and send it to osu! servers), then trigger
    # the processlist to be sent to bancho as well (also now unused).

    # this doesn't work on newer clients, and i had no plans
    # of trying to put it to use - just coded for completion.
    return write(ServerPackets.MONITOR)

# packet id: 81
@cache
def matchPlayerSkipped(pid: int) -> bytes:
    return write(
        ServerPackets.MATCH_PLAYER_SKIPPED,
        (pid, osuTypes.i32)
    )

# since the bot is always online and is
# also automatically added to all player's
# friends list, their presence is requested
# *very* frequently; only build it once.
@cache
def botPresence():
    return write(
        ServerPackets.USER_PRESENCE,
        (glob.bot.id, osuTypes.i32),
        (glob.bot.name, osuTypes.string),
        (-5 + 24, osuTypes.u8),
        (245, osuTypes.u8), # satellite provider
        (31, osuTypes.u8),
        (1234.0, osuTypes.f32), # send coordinates waaay
        (4321.0, osuTypes.f32), # off the map for the bot
        (0, osuTypes.i32)
    )

# packet id: 83
def userPresence(p: 'Player') -> bytes:
    if p is glob.bot:
        return botPresence()

    return write(
        ServerPackets.USER_PRESENCE,
        (p.id, osuTypes.i32),
        (p.name, osuTypes.string),
        (p.utc_offset + 24, osuTypes.u8),
        (p.geoloc['country']['numeric'], osuTypes.u8),
        (p.bancho_priv | (p.status.mode.as_vanilla << 5), osuTypes.u8),
        (p.geoloc['longitude'], osuTypes.f32),
        (p.geoloc['latitude'], osuTypes.f32),
        (p.gm_stats.rank, osuTypes.i32)
    )

# packet id: 86
@cache
def restartServer(ms: int) -> bytes:
    return write(
        ServerPackets.RESTART,
        (ms, osuTypes.i32)
    )

# packet id: 88
def matchInvite(p: 'Player', t_name: str) -> bytes:
    msg = f'Come join my game: {p.match.embed}.'
    return write(
        ServerPackets.MATCH_INVITE,
        ((p.name, msg, t_name, p.id), osuTypes.message)
    )

# packet id: 89
@cache
def channelInfoEnd() -> bytes:
    return write(ServerPackets.CHANNEL_INFO_END)

# packet id: 91
def matchChangePassword(new: str) -> bytes:
    return write(
        ServerPackets.MATCH_CHANGE_PASSWORD,
        (new, osuTypes.string)
    )

# packet id: 92
def silenceEnd(delta: int) -> bytes:
    return write(
        ServerPackets.SILENCE_END,
        (delta, osuTypes.i32)
    )

# packet id: 94
@cache
def userSilenced(pid: int) -> bytes:
    return write(
        ServerPackets.USER_SILENCED,
        (pid, osuTypes.i32)
    )

""" not sure why 95 & 96 exist? unused in gulag """

# packet id: 95
@cache
def userPresenceSingle(pid: int) -> bytes:
    return write(
        ServerPackets.USER_PRESENCE_SINGLE,
        (pid, osuTypes.i32)
    )

# packet id: 96
def userPresenceBundle(pid_list: list[int]) -> bytes:
    return write(
        ServerPackets.USER_PRESENCE_BUNDLE,
        (pid_list, osuTypes.i32_list)
    )

# packet id: 100
def userDMBlocked(target: str) -> bytes:
    return write(
        ServerPackets.USER_DM_BLOCKED,
        (('', '', target, 0), osuTypes.message)
    )

# packet id: 101
def targetSilenced(target: str) -> bytes:
    return write(
        ServerPackets.TARGET_IS_SILENCED,
        (('', '', target, 0), osuTypes.message)
    )

# packet id: 102
@cache
def versionUpdateForced() -> bytes:
    return write(ServerPackets.VERSION_UPDATE_FORCED)

# packet id: 103
def switchServer(t: int) -> bytes:
    # increment endpoint index if
    # idletime >= t && match == null
    return write(
        ServerPackets.SWITCH_SERVER,
        (t, osuTypes.i32)
    )

# packet id: 104
@cache
def accountRestricted() -> bytes:
    return write(ServerPackets.ACCOUNT_RESTRICTED)

# packet id: 105
# NOTE: deprecated
def RTX(msg: str) -> bytes:
    # bit of a weird one, sends a request to the client
    # to show some visual effects on screen for 5 seconds:
    # - black screen, freezes game, beeps loudly.
    # within the next 3-8 seconds at random.
    return write(
        ServerPackets.RTX,
        (msg, osuTypes.string)
    )

# packet id: 106
@cache
def matchAbort() -> bytes:
    return write(ServerPackets.MATCH_ABORT)

# packet id: 107
def switchTournamentServer(ip: str) -> bytes:
    # the client only reads the string if it's
    # not on the client's normal endpoints,
    # but we can send it either way xd.
    return write(
        ServerPackets.SWITCH_TOURNAMENT_SERVER,
        (ip, osuTypes.string)
    )
