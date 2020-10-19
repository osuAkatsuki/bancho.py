# -*- coding: utf-8 -*-

from typing import Any
from enum import IntEnum, unique
from typing import Optional
from functools import partialmethod, cache, lru_cache
from cmyui import log, Ansi
import struct

from objects import glob
from objects.beatmap import Beatmap
from objects.match import (Match, ScoreFrame, SlotStatus,
                           MatchTypes, MatchTeamTypes,
                           MatchScoringTypes, Teams)
from constants.types import osuTypes
from constants.gamemodes import GameMode
from constants.mods import Mods

# tuple of some of struct's format specifiers
# for clean access within packet pack/unpack.
_specifiers = (
    'b', 'B', # 8
    'h', 'H', # 16
    'i', 'I', 'f', # 32
    'q', 'Q', 'd'  # 64
)

@unique
class ClientPacketType(IntEnum):
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
        return f'<osu! Packet: {self.name} ({self.value})>'

@unique
class ServerPacketType(IntEnum):
    USER_ID = 5
    SEND_MESSAGE = 7
    PONG = 8
    HANDLE_IRC_CHANGE_USERNAME = 9
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
        return f'<Bancho Packet: {self.name} ({self.value})>'

class ClientPacket:
    """Abstract base class for incoming bancho packets."""
    type: Optional[ClientPacketType] = None
    args: Optional[tuple[osuTypes]] = None
    length: Optional[int] = None

    def __init_subclass__(cls, type: ClientPacketType, **kwargs) -> None:
        super().__init_subclass__(**kwargs)

        cls.type = type
        cls.args = cls.__annotations__

        for x in ('type', 'args', 'length'):
            if x in cls.args:
                del cls.args[x]

# TODO: should probably be.. not here :P
from collections import namedtuple
Message = namedtuple('Message', ['client', 'msg', 'target', 'client_id'])
Channel = namedtuple('Channel', ['name', 'topic', 'players'])

class BanchoPacketReader:
    """\
    A class dedicated to asynchronously reading bancho packets.

    Attributes
    -----------
    _buf: `memoryview`
        Internal buffer view of the reader.

    _current: Optional[`ClientPacket`]
        The current packet being read by the reader, if any.

    Intended Usage:
    ```
    async for packet in BanchoPacketReader(conn.body):
        # once you're ready to handle the packet,
        # simply call it's .handle() method.
        await packet.handle()
    ```
    """

    def __init__(self, data: bytes) -> None:
        self._buf = memoryview(data)
        self._current: Optional[ClientPacket] = None

    def __aiter__(self):
        return self

    async def __anext__(self):
        # do not break until we've read the
        # header of a packet we can handle.
        while True:
            p_type, p_len = await self.read_header()

            if p_type == ClientPacketType.PING:
                # the client is simply informing us that it's
                # still active; we don't have to handle anything.
                continue

            if p_type not in glob.bancho_map:
                # cannot handle - remove from
                # internal buffer and continue.
                log(f'Unhandled: {p_type!r}', Ansi.LYELLOW)

                if p_len != 0:
                    self._buf = self._buf[p_len:]
            else:
                # we can handle this one.
                break

        # we have a packet handler for this.
        self._current = glob.bancho_map[p_type]()
        self._current.length = p_len

        if self._current.args:
            await self.read_arguments()

        return self._current

    async def read_arguments(self) -> None:
        for arg_name, arg_type in self._current.args.items():
            # read value from buffer
            val = None

            # osu!-specific data types
            if arg_type == osuTypes.string:
                val = await self.read_string()
            elif arg_type == osuTypes.i32_list:
                val = await self.read_i32_list_i16l()
            elif arg_type == osuTypes.i32_list4l:
                val = await self.read_i32_list_i32l()
            elif arg_type == osuTypes.message:
                val = await self.read_message()
            elif arg_type == osuTypes.channel:
                val = await self.read_channel()
            elif arg_type == osuTypes.match:
                val = await self.read_match()
            elif arg_type == osuTypes.scoreframe:
                val = await self.read_scoreframe()

            # non-osu! datatypes
            elif arg_type == osuTypes.i8:
                val = await self.read_i8()
            elif arg_type == osuTypes.i16:
                val = await self.read_i16()
            elif arg_type == osuTypes.i32:
                val = await self.read_i32()
            elif arg_type == osuTypes.i64:
                val = await self.read_i64()
            elif arg_type == osuTypes.u8:
                val = await self.read_i8()
            elif arg_type == osuTypes.u16:
                val = await self.read_u16()
            elif arg_type == osuTypes.u32:
                val = await self.read_u32()
            elif arg_type == osuTypes.u64:
                val = await self.read_u64()

            elif arg_type == osuTypes.raw:
                # return all packet data raw.
                val = self._buf[:self._current.length]
                self._buf = self._buf[self._current.length:]
            else:
                # should never happen?
                raise ValueError

            # add to our packet object
            setattr(self._current, arg_name, val)

    async def read_header(self) -> tuple[int, int]:
        """Read the header of an osu! packet (id & length)."""
        if len(self._buf) < 7:
            # not even minimal data
            # remaining in buffer.
            # XXX: not sure if this works? lol
            raise StopAsyncIteration

        # read type & length from the body
        data = struct.unpack('<HxI', self._buf[:7])
        self._buf = self._buf[7:]
        return ClientPacketType(data[0]), data[1]

    async def ignore_packet(self) -> None:
        """Skip the current packet in the buffer."""
        self._buf = self._buf[self._current.length:]
        self._current = None

    """ simple types """

    async def read_uleb128(self) -> int:
        val = shift = 0

        while True:
            b = self._buf[0]
            self._buf = self._buf[1:]

            val |= ((b & 0b01111111) << shift)
            if (b & 0b10000000) == 0:
                break

            shift += 7

        return val

    async def read_string(self) -> str:
        exists = self._buf[0] == 0x0b
        self._buf = self._buf[1:]

        if not exists:
            # no string sent.
            return ''

        # non-empty string
        uleb = await self.read_uleb128()
        val = self._buf[:uleb].tobytes().decode() # copy
        self._buf = self._buf[uleb:]
        return val

    async def _read_integral(self, size: int, signed: bool) -> int:
        val = int.from_bytes(self._buf[:size], 'little', signed=signed)
        self._buf = self._buf[size:]
        return val

    read_i8 = partialmethod(_read_integral, size=1, signed=True)
    read_u8 = partialmethod(_read_integral, size=1, signed=False)
    read_i16 = partialmethod(_read_integral, size=2, signed=True)
    read_u16 = partialmethod(_read_integral, size=2, signed=False)
    read_i32 = partialmethod(_read_integral, size=4, signed=True)
    read_u32 = partialmethod(_read_integral, size=4, signed=False)
    read_i64 = partialmethod(_read_integral, size=8, signed=True)
    read_u64 = partialmethod(_read_integral, size=8, signed=False)

    async def read_f32(self) -> float:
        val = struct.unpack_from('<f', self._buf[:4])
        self._buf = self._buf[4:]
        return val

    async def read_f64(self) -> float:
        val = struct.unpack_from('<d', self._buf[:8])
        self._buf = self._buf[8:]
        return val

    async def _read_i32_list(self, len_size: int) -> tuple[int]:
        length = int.from_bytes(self._buf[:len_size], 'little')
        self._buf = self._buf[len_size:]

        val = struct.unpack(f'<{"I" * length}', self._buf[:length * 4])
        self._buf = self._buf[length * 4:]
        return val

    # XXX: some osu! packets use i16 for array length, some others use i32
    read_i32_list_i16l = partialmethod(_read_i32_list, len_size=2)
    read_i32_list_i32l = partialmethod(_read_i32_list, len_size=4)

    """ advanced types """
    # TODO: chan/msg could prolly have
    # classes of their own like match?

    async def read_message(self) -> Message:
        """Read an osu! message from the internal buffer."""
        return Message(
            client = await self.read_string(),
            msg = await self.read_string(),
            target = await self.read_string(),
            client_id = await self.read_i32()
        )

    async def read_channel(self) -> Channel:
        """Read an osu! channel from the internal buffer."""
        return Channel(
            name = await self.read_string(),
            topic = await self.read_string(),
            players = await self.read_i32()
        )

    async def read_match(self) -> Match:
        """Read an osu! match from the internal buffer."""
        m = Match()

        # ignore match id (i16) and inprogress (i8).
        self._buf = self._buf[3:]

        m.type = MatchTypes(await self.read_i8())
        m.mods = Mods(await self.read_i32())

        m.name = await self.read_string()
        m.passwd = await self.read_string()

        # ignore the map's name, we're going
        # to get all it's info from the md5.
        await self.read_string()

        map_id = await self.read_i32()
        map_md5 = await self.read_string()

        m.bmap = await Beatmap.from_md5(map_md5)
        if not m.bmap and map_id != (1 << 32) - 1:
            # if they pick an unsubmitted map,
            # just give them vivid [insane] lol.
            vivid_md5 = '1cf5b2c2edfafd055536d2cefcb89c0e'
            m.bmap = await Beatmap.from_md5(vivid_md5)

        for slot in m.slots:
            slot.status = await self.read_i8()

        for slot in m.slots:
            slot.team = Teams(await self.read_i8())

        for slot in m.slots:
            if slot.status & SlotStatus.has_player:
                # we don't need this, ignore it.
                self._buf = self._buf[4:]

        host_id = await self.read_i32()
        m.host = await glob.players.get_by_id(host_id)

        m.mode = GameMode(await self.read_i8())
        m.match_scoring = MatchScoringTypes(await self.read_i8())
        m.team_type = MatchTeamTypes(await self.read_i8())
        m.freemods = await self.read_i8() == 1

        # if we're in freemods mode,
        # read individual slot mods.
        if m.freemods:
            for slot in m.slots:
                slot.mods = Mods(await self.read_i32())

        # read the seed (used for mania)
        m.seed = await self.read_i32()

        return m

    async def read_scoreframe(self) -> ScoreFrame:
        fmt = '<iBHHHHHHiHH?BB?'
        sf = ScoreFrame(struct.unpack_from(fmt, self._buf[:29]))
        self._buf = self._buf[29:]

        if sf.score_v2:
            sf.combo_portion = await self.read_f32()
            sf.bonus_portion = await self.read_f32()

        return sf

def write_uleb128(num: int) -> bytearray:
    """ Write `num` into an unsigned LEB128. """
    if num == 0:
        return bytearray(b'\x00')

    ret = bytearray()
    length = 0

    while num > 0:
        ret.append(num & 127)
        num >>= 7
        if num != 0:
            ret[length] |= 128
        length += 1

    return ret

def write_string(s: str) -> bytearray:
    """ Write `s` into bytes (ULEB128 & string). """
    if (length := len(s)) > 0:
        # non-empty string
        data = b'\x0b' + write_uleb128(length) + s.encode()
    else:
        # empty string
        data = b'\x00'

    return bytearray(data)

def write_i32_list(l: tuple[int, ...]) -> bytearray:
    """ Write `l` into bytes (int32 list). """
    ret = bytearray(len(l).to_bytes(2, 'little'))

    for i in l:
        ret.extend(i.to_bytes(4, 'little'))

    return ret

def write_message(client: str, msg: str, target: str,
                        client_id: int) -> bytearray:
    """ Write params into bytes (osu! message). """
    return bytearray(
        write_string(client) +
        write_string(msg) +
        write_string(target) +
        client_id.to_bytes(4, 'little', signed=True)
    )

def write_channel(name: str, topic: str,
                        count: int) -> bytearray:
    """ Write params into bytes (osu! channel). """
    return bytearray(
        write_string(name) +
        write_string(topic) +
        count.to_bytes(2, 'little')
    )

# XXX: deprecated
# def write_mapInfoReply(maps: Sequence[BeatmapInfo]) -> bytearray:
#     """ Write `maps` into bytes (osu! map info). """
#     ret = bytearray(len(maps).to_bytes(4, 'little'))
#
#     # Write files
#     for m in maps:
#         ret.extend(struct.pack('<hiiiBbbbb',
#             m.id, m.map_id, m.set_id, m.thread_id, m.status,
#             m.osu_rank, m.fruits_rank, m.taiko_rank, m.mania_rank
#         ))
#         ret.extend(write_string(m.map_md5))
#
#     return ret

def write_match(m: Match) -> bytearray:
    """ Write `m` into bytes (osu! match). """
    ret = bytearray(
        struct.pack('<HbbI', m.id, m.in_progress, m.type, m.mods) +
        write_string(m.name) +
        write_string(m.passwd)
    )

    if m.bmap:
        ret.extend(write_string(m.bmap.full))
        ret.extend(m.bmap.id.to_bytes(4, 'little'))
        ret.extend(write_string(m.bmap.md5))
    else:
        ret.extend(write_string('')) # name
        ret.extend(((1 << 32) - 1).to_bytes(4, 'little')) # id
        ret.extend(write_string('')) # md5

    ret.extend(s.status for s in m.slots)
    ret.extend(s.team for s in m.slots)

    for s in m.slots:
        if s.player:
            ret.extend(s.player.id.to_bytes(4, 'little'))

    ret.extend(m.host.id.to_bytes(4, 'little'))
    ret.extend((m.mode, m.match_scoring,
                m.team_type, m.freemods))

    if m.freemods:
        for s in m.slots:
            ret.extend(s.mods.to_bytes(4, 'little'))

    ret.extend(m.seed.to_bytes(4, 'little'))
    return ret

def write_scoreframe(s: ScoreFrame) -> bytearray:
    """ Write `s` into bytes (osu! scoreframe). """
    return bytearray(struct.pack('<ibHHHHHHIIbbbb',
        s.time, s.id, s.num300, s.num100, s.num50, s.num_geki,
        s.num_katu, s.num_miss, s.total_score, s.max_combo,
        s.perfect, s.current_hp, s.tag_byte, s.score_v2
    ))

def write(packid: int, *args: tuple[Any, ...]) -> bytes:
    """ Write `args` into bytes. """
    ret = bytearray(struct.pack('<Hx', packid))

    for p, p_type in args:
        if p_type == osuTypes.raw:
            ret.extend(p)
        elif p_type == osuTypes.string:
            ret.extend(write_string(p))
        elif p_type == osuTypes.i32_list:
            ret.extend(write_i32_list(p))
        elif p_type == osuTypes.message:
            ret.extend(write_message(*p))
        elif p_type == osuTypes.channel:
            ret.extend(write_channel(*p))
        elif p_type == osuTypes.match:
            ret.extend(write_match(p))
        elif p_type == osuTypes.scoreframe:
            ret.extend(write_scoreframe(p))
        #elif p_type == osuTypes.mapInfoReply:
        #    ret.extend(write_mapInfoReply(p))
        else:
            # not a custom type, use struct to pack the data.
            ret.extend(struct.pack(f'<{_specifiers[p_type]}', p))

    # add size
    ret[3:3] = struct.pack('<I', len(ret) - 3)
    return ret

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
        ServerPacketType.USER_ID,
        (id, osuTypes.i32)
    )

# packet id: 7
def sendMessage(client: str, msg: str, target: str,
                client_id: int) -> bytes:
    return write(
        ServerPacketType.SEND_MESSAGE,
        ((client, msg, target, client_id), osuTypes.message)
    )

# packet id: 8
@cache
def pong() -> bytes:
    return write(ServerPacketType.PONG)

# packet id: 9
def changeUsername(old: str, new: str) -> bytes:
    return write(
        ServerPacketType.HANDLE_IRC_CHANGE_USERNAME,
        (f'{old}>>>>{new}', osuTypes.string)
    )

# packet id: 11
def userStats(p) -> bytes:
    return write(
        ServerPacketType.USER_STATS,
        (p.id, osuTypes.i32),
        (p.status.action, osuTypes.u8),
        (p.status.info_text, osuTypes.string),
        (p.status.map_md5, osuTypes.string),
        (p.status.mods, osuTypes.i32),
        (p.status.mode.as_vanilla, osuTypes.u8),
        (p.status.map_id, osuTypes.i32),
        (p.gm_stats.rscore, osuTypes.i64),
        (p.gm_stats.acc / 100.0, osuTypes.f32),
        (p.gm_stats.plays, osuTypes.i32),
        (p.gm_stats.tscore, osuTypes.i64),
        (p.gm_stats.rank, osuTypes.i32),
        (p.gm_stats.pp, osuTypes.i16)
    ) if p.id != 1 else ( # default for bot
        b'\x0b\x00\x00=\x00\x00\x00\x01\x00\x00'
        b'\x00\x08\x0b\x0eout new code..\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x80?'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    )

# packet id: 12
@cache
def logout(userID: int) -> bytes:
    return write(
        ServerPacketType.USER_LOGOUT,
        (userID, osuTypes.i32),
        (0, osuTypes.u8)
    )

# packet id: 13
@cache
def spectatorJoined(id: int) -> bytes:
    return write(
        ServerPacketType.SPECTATOR_JOINED,
        (id, osuTypes.i32)
    )

# packet id: 14
@cache
def spectatorLeft(id: int) -> bytes:
    return write(
        ServerPacketType.SPECTATOR_LEFT,
        (id, osuTypes.i32)
    )

# packet id: 15
def spectateFrames(data: bytearray) -> bytes:
    return ( # a little hacky, but quick.
        ServerPacketType.SPECTATE_FRAMES.to_bytes(
            3, 'little', signed = True
        ) + len(data).to_bytes(4, 'little') + data
    )

# packet id: 19
@cache
def versionUpdate() -> bytes:
    return write(ServerPacketType.VERSION_UPDATE)

# packet id: 22
@cache
def spectatorCantSpectate(id: int) -> bytes:
    return write(
        ServerPacketType.SPECTATOR_CANT_SPECTATE,
        (id, osuTypes.i32)
    )

# packet id: 23
@cache
def getAttention() -> bytes:
    return write(ServerPacketType.GET_ATTENTION)

# packet id: 24
@lru_cache(maxsize=4)
def notification(msg: str) -> bytes:
    return write(
        ServerPacketType.NOTIFICATION,
        (msg, osuTypes.string)
    )

# packet id: 26
def updateMatch(m: Match) -> bytes:
    return write(
        ServerPacketType.UPDATE_MATCH,
        (m, osuTypes.match)
    )

# packet id: 27
def newMatch(m: Match) -> bytes:
    return write(
        ServerPacketType.NEW_MATCH,
        (m, osuTypes.match)
    )

# packet id: 28
@cache
def disposeMatch(id: int) -> bytes:
    return write(
        ServerPacketType.DISPOSE_MATCH,
        (id, osuTypes.i32)
    )

# packet id: 34
@cache
def toggleBlockNonFriendPM() -> bytes:
    return write(ServerPacketType.TOGGLE_BLOCK_NON_FRIEND_DMS)

# packet id: 36
def matchJoinSuccess(m: Match) -> bytes:
    return write(
        ServerPacketType.MATCH_JOIN_SUCCESS,
        (m, osuTypes.match)
    )

# packet id: 37
@cache
def matchJoinFail() -> bytes:
    return write(ServerPacketType.MATCH_JOIN_FAIL)

# packet id: 42
@cache
def fellowSpectatorJoined(id: int) -> bytes:
    return write(
        ServerPacketType.FELLOW_SPECTATOR_JOINED,
        (id, osuTypes.i32)
    )

# packet id: 43
@cache
def fellowSpectatorLeft(id: int) -> bytes:
    return write(
        ServerPacketType.FELLOW_SPECTATOR_LEFT,
        (id, osuTypes.i32)
    )

# packet id: 46
def matchStart(m: Match) -> bytes:
    return write(
        ServerPacketType.MATCH_START,
        (m, osuTypes.match)
    )

# packet id: 48
def matchScoreUpdate(frame: ScoreFrame) -> bytes:
    return write(
        ServerPacketType.MATCH_SCORE_UPDATE,
        (frame, osuTypes.scoreframe)
    )

# packet id: 50
@cache
def matchTransferHost() -> bytes:
    return write(ServerPacketType.MATCH_TRANSFER_HOST)

# packet id: 53
@cache
def matchAllPlayerLoaded() -> bytes:
    return write(ServerPacketType.MATCH_ALL_PLAYERS_LOADED)

# packet id: 57
@cache
def matchPlayerFailed(slot_id: int) -> bytes:
    return write(
        ServerPacketType.MATCH_PLAYER_FAILED,
        (slot_id, osuTypes.i32)
    )

# packet id: 58
@cache
def matchComplete() -> bytes:
    return write(ServerPacketType.MATCH_COMPLETE)

# packet id: 61
@cache
def matchSkip() -> bytes:
    return write(ServerPacketType.MATCH_SKIP)

# packet id: 64
@lru_cache(maxsize=8)
def channelJoin(name: str) -> bytes:
    return write(
        ServerPacketType.CHANNEL_JOIN_SUCCESS,
        (name, osuTypes.string)
    )

# packet id: 65
@lru_cache(maxsize=8)
def channelInfo(name: str, topic: str,
                p_count: int) -> bytes:
    return write(
        ServerPacketType.CHANNEL_INFO,
        ((name, topic, p_count), osuTypes.channel)
    )

# packet id: 66
@lru_cache(maxsize=8)
def channelKick(name: str) -> bytes:
    return write(
        ServerPacketType.CHANNEL_KICK,
        (name, osuTypes.string)
    )

# packet id: 67
@lru_cache(maxsize=8)
def channelAutoJoin(name: str, topic: str,
                    p_count: int) -> bytes:
    return write(
        ServerPacketType.CHANNEL_AUTO_JOIN,
        ((name, topic, p_count), osuTypes.channel)
    )

# packet id: 69
#def beatmapInfoReply(maps: Sequence[BeatmapInfo]) -> bytes:
#    return write(
#        ServerPacketType.BEATMAP_INFO_REPLY,
#        (maps, osuTypes.mapInfoReply)
#    )

# packet id: 71
@cache
def banchoPrivileges(priv: int) -> bytes:
    return write(
        ServerPacketType.PRIVILEGES,
        (priv, osuTypes.i32)
    )

# packet id: 72
def friendsList(*friends) -> bytes:
    return write(
        ServerPacketType.FRIENDS_LIST,
        (friends, osuTypes.i32_list)
    )

# packet id: 75
@cache
def protocolVersion(ver: int) -> bytes:
    return write(
        ServerPacketType.PROTOCOL_VERSION,
        (ver, osuTypes.i32)
    )

# packet id: 76
@cache
def mainMenuIcon() -> bytes:
    return write(
        ServerPacketType.MAIN_MENU_ICON,
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
    return write(ServerPacketType.MONITOR)

# packet id: 81
@cache
def matchPlayerSkipped(pid: int) -> bytes:
    return write(
        ServerPacketType.MATCH_PLAYER_SKIPPED,
        (pid, osuTypes.i32)
    )

# packet id: 83
def userPresence(p) -> bytes:
    return write(
        ServerPacketType.USER_PRESENCE,
        (p.id, osuTypes.i32),
        (p.name, osuTypes.string),
        (p.utc_offset + 24, osuTypes.u8),
        (p.country[0], osuTypes.u8),
        (p.bancho_priv | (p.status.mode.as_vanilla << 5), osuTypes.u8),
        (p.location[0], osuTypes.f32), # long
        (p.location[1], osuTypes.f32), # lat
        (p.gm_stats.rank, osuTypes.i32)
    ) if p.id != 1 else ( # default for bot
        b'S\x00\x00\x19\x00\x00\x00\x01\x00\x00\x00'
        b'\x0b\x04Aika\x14&\x1f\x00\x00\x9d\xc2\x00'
        b'\x000B\x00\x00\x00\x00'
    )

# packet id: 86
@cache
def restartServer(ms: int) -> bytes:
    return write(
        ServerPacketType.RESTART,
        (ms, osuTypes.i32)
    )

# packet id: 88
@lru_cache(maxsize=4)
def matchInvite(p, t_name: str) -> bytes:
    msg = f'Come join my game: {p.match.embed}.'
    return write(
        ServerPacketType.MATCH_INVITE,
        ((p.name, msg, t_name, p.id), osuTypes.message)
    )

# packet id: 89
@cache
def channelInfoEnd() -> bytes:
    return write(ServerPacketType.CHANNEL_INFO_END)

# packet id: 91
def matchChangePassword(new: str) -> bytes:
    return write(
        ServerPacketType.MATCH_CHANGE_PASSWORD,
        (new, osuTypes.string)
    )

# packet id: 92
def silenceEnd(delta: int) -> bytes:
    return write(
        ServerPacketType.SILENCE_END,
        (delta, osuTypes.i32)
    )

# packet id: 94
@cache
def userSilenced(pid: int) -> bytes:
    return write(
        ServerPacketType.USER_SILENCED,
        (pid, osuTypes.i32)
    )

""" not sure why 95 & 96 exist? unused in gulag """

# packet id: 95
@cache
def userPresenceSingle(pid: int) -> bytes:
    return write(
        ServerPacketType.USER_PRESENCE_SINGLE,
        (pid, osuTypes.i32)
    )

# packet id: 96
def userPresenceBundle(pid_list: list[int]) -> bytes:
    return write(
        ServerPacketType.USER_PRESENCE_BUNDLE,
        (pid_list, osuTypes.i32_list)
    )

# packet id: 100
def userDMBlocked(target: str) -> bytes:
    return write(
        ServerPacketType.USER_DM_BLOCKED,
        (('', '', target, 0), osuTypes.message)
    )

# packet id: 101
def targetSilenced(target: str) -> bytes:
    return write(
        ServerPacketType.TARGET_IS_SILENCED,
        (('', '', target, 0), osuTypes.message)
    )

# packet id: 102
@cache
def versionUpdateForced() -> bytes:
    return write(ServerPacketType.VERSION_UPDATE_FORCED)

# packet id: 103
def switchServer(t: int) -> bytes: # (idletime < t || match != null)
    return write(
        ServerPacketType.SWITCH_SERVER,
        (t, osuTypes.i32)
    )

# packet id: 104
@cache
def accountRestricted() -> bytes:
    return write(ServerPacketType.ACCOUNT_RESTRICTED)

# packet id: 105
# NOTE: deprecated
def RTX(msg: str) -> bytes:
    # bit of a weird one, sends a request to the client
    # to show some visual effects on screen for 5 seconds:
    # - black screen, freezes game, beeps loudly.
    # within the next 3-8 seconds at random.
    return write(
        ServerPacketType.RTX,
        (msg, osuTypes.string)
    )

# packet id: 106
@cache
def matchAbort() -> bytes:
    return write(ServerPacketType.MATCH_ABORT)

# packet id: 107
def switchTournamentServer(ip: str) -> bytes:
    # the client only reads the string if it's
    # not on the client's normal endpoints,
    # but we can send it either way xd.
    return write(
        ServerPacketType.SWITCH_TOURNAMENT_SERVER,
        (ip, osuTypes.string)
    )
