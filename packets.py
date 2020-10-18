# -*- coding: utf-8 -*-

from typing import Any
from enum import IntEnum, unique
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
    'b', 'B',  # 8
    'h', 'H',  # 16
    'i', 'I', 'f',  # 32
    'q', 'Q', 'd'  # 64
)


async def read_uleb128(data: memoryview) -> tuple[int, int]:
    """ Read an unsigned LEB128 (used for string length) from `data`. """
    offset = val = shift = 0

    while True:
        b = data[offset]
        offset += 1

        val |= ((b & 0b01111111) << shift)
        if (b & 0b10000000) == 0x00:
            break

        shift += 7

    return val, offset


async def read_string(data: memoryview) -> tuple[str, int]:
    """ Read a string (ULEB128 & string) from `data`. """
    offset = 1

    if data[0] == 0x00:
        return '', offset

    length, offs = await read_uleb128(data[offset:])
    offset += offs

    return data[offset:offset+length].tobytes().decode(), offset + length


async def read_i32_list(data: memoryview, long_len: bool = False
                        ) -> tuple[tuple[int, ...], int]:
    """ Read an int32 list from `data`. """
    ret = []
    offs = 4 if long_len else 2

    for _ in range(int.from_bytes(data[:offs], 'little')):
        ret.append(int.from_bytes(data[offs:offs+4], 'little'))
        offs += 4

    return ret, offs


async def read_match(data: memoryview) -> tuple[Match, int]:
    """ Read an osu! match from `data`. """
    m = Match()

    # ignore match id (i32) & inprogress (i8).
    offset = 3

    # read match type (no idea what this is tbh).
    m.type = MatchTypes(data[offset])
    offset += 1

    # read match mods.
    m.mods = Mods.from_bytes(data[offset:offset+4], 'little')
    offset += 4

    # read match name & password.
    m.name, offs = await read_string(data[offset:])
    offset += offs
    m.passwd, offs = await read_string(data[offset:])
    offset += offs

    # ignore map's name.
    if data[offset] == 0x0b:
        offset += sum(await read_uleb128(data[offset + 1:]))
    offset += 1

    # read beatmap information (id & md5).
    map_id = int.from_bytes(data[offset:offset+4], 'little')
    offset += 4

    map_md5, offs = await read_string(data[offset:])
    offset += offs

    # get beatmap object for map selected.
    m.bmap = await Beatmap.from_md5(map_md5)
    if not m.bmap and map_id != (1 << 32) - 1:
        # if they pick an unsubmitted map,
        # just give them vivid [insane] lol.
        vivid_md5 = '1cf5b2c2edfafd055536d2cefcb89c0e'
        m.bmap = await Beatmap.from_md5(vivid_md5)

    # read slot statuses.
    for s in m.slots:
        s.status = data[offset]
        offset += 1

    # read slot teams.
    for s in m.slots:
        s.team = Teams(data[offset])
        offset += 1

    for s in m.slots:
        if s.status & SlotStatus.has_player:
            # i don't think we need this?
            offset += 4

    # read match host.
    user_id = int.from_bytes(data[offset:offset+4], 'little')
    m.host = await glob.players.get_by_id(user_id)
    offset += 4

    # read match mode, match scoring,
    # team type, and freemods.
    m.mode = GameMode(data[offset])
    offset += 1
    m.match_scoring = MatchScoringTypes(data[offset])
    offset += 1
    m.team_type = MatchTeamTypes(data[offset])
    offset += 1
    m.freemods = data[offset] == 1
    offset += 1

    # if we're in freemods mode,
    # read individual slot mods.
    if m.freemods:
        for s in m.slots:
            s.mods = Mods.from_bytes(data[offset:offset+4], 'little')
            offset += 4

    # read the seed from multi.
    # XXX: used for mania random mod.
    m.seed = int.from_bytes(data[offset:offset+4], 'little')
    return m, offset + 4


async def read_scoreframe(data: memoryview) -> tuple[ScoreFrame, int]:
    """ Read an osu! scoreframe from `data`. """
    offset = 29
    s = ScoreFrame(*struct.unpack('<iBHHHHHHiHH?BB?', data[:offset]))

    if s.score_v2:
        s.combo_portion, s.bonus_portion = struct.unpack(
            '<ff', data[offset:offset+8])
        offset += 8

    return s, offset

# XXX: deprecated
# async def read_mapInfoRequest(data: memoryview) -> tuple[Beatmap, int]:
#     """ Read an osu! beatmapInfoRequest from `data`. """
#     fnames = ids = []
#
#     # read filenames
#     offset = 4
#     for _ in range(int.from_bytes(data[:offset], 'little')): # filenames
#         fname, offs = await read_string(data[offset:])
#         offset += offs
#         fnames.append(fname)
#
#     # read ids
#     ids, offs = await read_i32_list(data[offset:], long_len=True)
#     return BeatmapInfoRequest(fnames, ids), offset + offs


class BanchoPacketReader:
    """A class dedicated to reading osu! bancho packets.

    Attributes
    -----------
    _buf: `memoryview`
        Internal buffer of the reader.
        XXX: Use the `data` property to have data
             starting from the current internal offset.

    _offset: `int`
        The offset of the reader; bytes behind the offset have
        already been read, bytes ahead are yet to be read.

    current_packet: Optional[`BanchoPacket`]
        The current packet being processed by the reader.
        XXX: will be None if either no packets have been read,
             or if the current packet was corrupt.

    length: `int`
        The length (in bytes) of the current packet.

    Properties
    -----------
    data: `bytearray`
        The data starting from the current offset.
    """
    __slots__ = ('_buf', '_offset',
                 'current_packet', 'length')

    def __init__(self, data: bytes):  # `data` is the request body
        self._buf = memoryview(data)
        self._offset = 0

        self.current_packet = None
        self.length = 0

    @property
    def data(self) -> memoryview:
        return self._buf[self._offset:]

    def empty(self) -> bool:
        return self._offset >= len(self._buf)

    def ignore(self, count: int) -> None:
        self._offset += count

    def ignore_packet(self) -> None:
        self._offset += self.length

    async def read_packet_header(self) -> None:
        ldata = len(self.data)

        if ldata < 7:
            # packet not even minimal legnth.
            # end the connection immediately.
            self.current_packet = None
            self._offset += ldata
            log(f'[ERR] Data misread! (len: {len(self.data)})', Ansi.LRED)
            return

        packet_id, self.length = struct.unpack('<HxI', self.data[:7])
        self.current_packet = ClientPacket(packet_id)

        self._offset += 7  # read first 7 bytes for packetid & length

    async def read(self, *types: tuple[osuTypes, ...]) -> tuple[Any, ...]:
        ret = []

        # iterate through all types to be read.
        for t in types:
            if t == osuTypes.string:
                # read a string
                data, offs = await read_string(self.data)
                self._offset += offs
                if data is not None:
                    ret.append(data)
            elif t in (osuTypes.i32_list, osuTypes.i32_list4l):
                # read an i32 list
                _longlen = t == osuTypes.i32_list4l
                data, offs = await read_i32_list(self.data, _longlen)
                self._offset += offs
                if data is not None:
                    ret.extend(data)
            elif t == osuTypes.channel:
                # read an osu! channel
                for _ in range(2):
                    data, offs = await read_string(self.data)
                    self._offset += offs
                    if data is not None:
                        ret.append(data)
                ret.append(int.from_bytes(self.data[:2], 'little'))
                self._offset += 2
            elif t == osuTypes.message:
                # read an osu! message
                for _ in range(3):
                    data, offs = await read_string(self.data)
                    self._offset += offs
                    if data is not None:
                        ret.append(data)
                ret.append(int.from_bytes(self.data[:4], 'little'))
                self._offset += 4
            elif t == osuTypes.match:
                # read an osu! match
                data, offs = await read_match(self.data)
                self._offset += offs
                ret.append(data)
            elif t == osuTypes.scoreframe:
                # read an osu! scoreframe
                data, offs = await read_scoreframe(self.data)
                self._offset += offs
            # elif t == osuTypes.mapInfoRequest:
            #    # read an osu! beatmapInfoRequest.
            #    data, offs = await read_mapInfoRequest(self.data)
            #    self._offset += offs
            #    ret.append(data)
            else:
                # read a normal datatype
                fmt = _specifiers[t]
                size = struct.calcsize(fmt)
                ret.extend(struct.unpack(fmt, self.data[:size]))
                self._offset += size

        return ret


async def write_uleb128(num: int) -> bytearray:
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


async def write_string(s: str) -> bytearray:
    """ Write `s` into bytes (ULEB128 & string). """
    if (length := len(s)) > 0:
        # non-empty string
        data = b'\x0b' + await write_uleb128(length) + s.encode()
    else:
        # empty string
        data = b'\x00'

    return bytearray(data)


async def write_i32_list(l: tuple[int, ...]) -> bytearray:
    """ Write `l` into bytes (int32 list). """
    ret = bytearray(len(l).to_bytes(2, 'little'))

    for i in l:
        ret.extend(i.to_bytes(4, 'little'))

    return ret


async def write_message(client: str, msg: str, target: str,
                        client_id: int) -> bytearray:
    """ Write params into bytes (osu! message). """
    return bytearray(
        await write_string(client) +
        await write_string(msg) +
        await write_string(target) +
        client_id.to_bytes(4, 'little', signed=True)
    )


async def write_channel(name: str, topic: str,
                        count: int) -> bytearray:
    """ Write params into bytes (osu! channel). """
    return bytearray(
        await write_string(name) +
        await write_string(topic) +
        count.to_bytes(2, 'little')
    )

# XXX: deprecated
# async def write_mapInfoReply(maps: Sequence[BeatmapInfo]) -> bytearray:
#     """ Write `maps` into bytes (osu! map info). """
#     ret = bytearray(len(maps).to_bytes(4, 'little'))
#
#     # Write files
#     for m in maps:
#         ret.extend(struct.pack('<hiiiBbbbb',
#             m.id, m.map_id, m.set_id, m.thread_id, m.status,
#             m.osu_rank, m.fruits_rank, m.taiko_rank, m.mania_rank
#         ))
#         ret.extend(await write_string(m.map_md5))
#
#     return ret


async def write_match(m: Match) -> bytearray:
    """ Write `m` into bytes (osu! match). """
    ret = bytearray(
        struct.pack('<HbbI', m.id, m.in_progress, m.type, m.mods) +
        await write_string(m.name) +
        await write_string(m.passwd)
    )

    if m.bmap:
        ret.extend(await write_string(m.bmap.full))
        ret.extend(m.bmap.id.to_bytes(4, 'little'))
        ret.extend(await write_string(m.bmap.md5))
    else:
        ret.extend(await write_string(''))  # name
        ret.extend(((1 << 32) - 1).to_bytes(4, 'little'))  # id
        ret.extend(await write_string(''))  # md5

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


async def write_scoreframe(s: ScoreFrame) -> bytearray:
    """ Write `s` into bytes (osu! scoreframe). """
    return bytearray(struct.pack('<ibHHHHHHIIbbbb',
                                 s.time, s.id, s.num300, s.num100, s.num50, s.num_geki,
                                 s.num_katu, s.num_miss, s.total_score, s.max_combo,
                                 s.perfect, s.current_hp, s.tag_byte, s.score_v2
                                 ))


async def write(packid: int, *args: tuple[Any, ...]) -> bytes:
    """ Write `args` into bytes. """
    ret = bytearray(struct.pack('<Hx', packid))

    for p, p_type in args:
        if p_type == osuTypes.raw:
            ret.extend(p)
        elif p_type == osuTypes.string:
            ret.extend(await write_string(p))
        elif p_type == osuTypes.i32_list:
            ret.extend(await write_i32_list(p))
        elif p_type == osuTypes.message:
            ret.extend(await write_message(*p))
        elif p_type == osuTypes.channel:
            ret.extend(await write_channel(*p))
        elif p_type == osuTypes.match:
            ret.extend(await write_match(p))
        elif p_type == osuTypes.scoreframe:
            ret.extend(await write_scoreframe(p))
        # elif p_type == osuTypes.mapInfoReply:
        #    ret.extend(await write_mapInfoReply(p))
        else:
            # not a custom type, use struct to pack the data.
            ret.extend(struct.pack(f'<{_specifiers[p_type]}', p))

    # add size
    ret[3:3] = struct.pack('<I', len(ret) - 3)
    return ret


@unique
class ClientPacket(IntEnum):
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
class ServerPacket(IntEnum):
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
        return f'<Bancho Packet: {self.name} ({self.value})>'

#
# packets
#

# packet id: 5


async def userID(id: int) -> bytes:
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
    return await write(
        ServerPacket.USER_ID,
        (id, osuTypes.i32)
    )

# packet id: 7


async def sendMessage(client: str, msg: str, target: str,
                      client_id: int) -> bytes:
    return await write(
        ServerPacket.SEND_MESSAGE,
        ((client, msg, target, client_id), osuTypes.message)
    )

# packet id: 8


async def pong() -> bytes:
    return await write(ServerPacket.PONG)

# packet id: 9


async def changeUsername(old: str, new: str) -> bytes:
    return await write(
        ServerPacket.HANDLE_IRC_CHANGE_USERNAME,
        (f'{old}>>>>{new}', osuTypes.string)
    )

# packet id: 11


async def userStats(p) -> bytes:
    return await write(
        ServerPacket.USER_STATS,
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
    ) if p.id != 1 else (  # default for bot
        b'\x0b\x00\x00=\x00\x00\x00\x01\x00\x00'
        b'\x00\x08\x0b\x0eout new code..\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x80?'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    )

# packet id: 12


async def logout(userID: int) -> bytes:
    return await write(
        ServerPacket.USER_LOGOUT,
        (userID, osuTypes.i32),
        (0, osuTypes.u8)
    )

# packet id: 13


async def spectatorJoined(id: int) -> bytes:
    return await write(
        ServerPacket.SPECTATOR_JOINED,
        (id, osuTypes.i32)
    )

# packet id: 14


async def spectatorLeft(id: int) -> bytes:
    return await write(
        ServerPacket.SPECTATOR_LEFT,
        (id, osuTypes.i32)
    )

# packet id: 15


async def spectateFrames(data: bytearray) -> bytes:
    return (  # a little hacky, but quick.
        ServerPacket.SPECTATE_FRAMES.to_bytes(
            3, 'little', signed=True
        ) + len(data).to_bytes(4, 'little') + data
    )

# packet id: 19


async def versionUpdate() -> bytes:
    return await write(ServerPacket.VERSION_UPDATE)

# packet id: 22


async def spectatorCantSpectate(id: int) -> bytes:
    return await write(
        ServerPacket.SPECTATOR_CANT_SPECTATE,
        (id, osuTypes.i32)
    )

# packet id: 23


async def getAttention() -> bytes:
    return await write(ServerPacket.GET_ATTENTION)

# packet id: 24


async def notification(msg: str) -> bytes:
    return await write(
        ServerPacket.NOTIFICATION,
        (msg, osuTypes.string)
    )

# packet id: 26


async def updateMatch(m: Match) -> bytes:
    return await write(
        ServerPacket.UPDATE_MATCH,
        (m, osuTypes.match)
    )

# packet id: 27


async def newMatch(m: Match) -> bytes:
    return await write(
        ServerPacket.NEW_MATCH,
        (m, osuTypes.match)
    )

# packet id: 28


async def disposeMatch(id: int) -> bytes:
    return await write(
        ServerPacket.DISPOSE_MATCH,
        (id, osuTypes.i32)
    )

# packet id: 34


async def toggleBlockNonFriendPM() -> bytes:
    return await write(ServerPacket.TOGGLE_BLOCK_NON_FRIEND_DMS)

# packet id: 36


async def matchJoinSuccess(m: Match) -> bytes:
    return await write(
        ServerPacket.MATCH_JOIN_SUCCESS,
        (m, osuTypes.match)
    )

# packet id: 37


async def matchJoinFail() -> bytes:
    return await write(ServerPacket.MATCH_JOIN_FAIL)

# packet id: 42


async def fellowSpectatorJoined(id: int) -> bytes:
    return await write(
        ServerPacket.FELLOW_SPECTATOR_JOINED,
        (id, osuTypes.i32)
    )

# packet id: 43


async def fellowSpectatorLeft(id: int) -> bytes:
    return await write(
        ServerPacket.FELLOW_SPECTATOR_LEFT,
        (id, osuTypes.i32)
    )

# packet id: 46


async def matchStart(m: Match) -> bytes:
    return await write(
        ServerPacket.MATCH_START,
        (m, osuTypes.match)
    )

# packet id: 48


async def matchScoreUpdate(frame: ScoreFrame) -> bytes:
    return await write(
        ServerPacket.MATCH_SCORE_UPDATE,
        (frame, osuTypes.scoreframe)
    )

# packet id: 50


async def matchTransferHost() -> bytes:
    return await write(ServerPacket.MATCH_TRANSFER_HOST)

# packet id: 53


async def matchAllPlayerLoaded() -> bytes:
    return await write(ServerPacket.MATCH_ALL_PLAYERS_LOADED)

# packet id: 57


async def matchPlayerFailed(slot_id: int) -> bytes:
    return await write(
        ServerPacket.MATCH_PLAYER_FAILED,
        (slot_id, osuTypes.i32)
    )

# packet id: 58


async def matchComplete() -> bytes:
    return await write(ServerPacket.MATCH_COMPLETE)

# packet id: 61


async def matchSkip() -> bytes:
    return await write(ServerPacket.MATCH_SKIP)

# packet id: 64


async def channelJoin(name: str) -> bytes:
    return await write(
        ServerPacket.CHANNEL_JOIN_SUCCESS,
        (name, osuTypes.string)
    )

# packet id: 65


async def channelInfo(name: str, topic: str,
                      p_count: int) -> bytes:
    return await write(
        ServerPacket.CHANNEL_INFO,
        ((name, topic, p_count), osuTypes.channel)
    )

# packet id: 66


async def channelKick(name: str) -> bytes:
    return await write(
        ServerPacket.CHANNEL_KICK,
        (name, osuTypes.string)
    )

# packet id: 67


async def channelAutoJoin(name: str, topic: str,
                          p_count: int) -> bytes:
    return await write(
        ServerPacket.CHANNEL_AUTO_JOIN,
        ((name, topic, p_count), osuTypes.channel)
    )

# packet id: 69
# async def beatmapInfoReply(maps: Sequence[BeatmapInfo]) -> bytes:
#    return await write(
#        ServerPacket.BEATMAP_INFO_REPLY,
#        (maps, osuTypes.mapInfoReply)
#    )

# packet id: 71


async def banchoPrivileges(priv: int) -> bytes:
    return await write(
        ServerPacket.PRIVILEGES,
        (priv, osuTypes.i32)
    )

# packet id: 72


async def friendsList(*friends) -> bytes:
    return await write(
        ServerPacket.FRIENDS_LIST,
        (friends, osuTypes.i32_list)
    )

# packet id: 75


async def protocolVersion(ver: int) -> bytes:
    return await write(
        ServerPacket.PROTOCOL_VERSION,
        (ver, osuTypes.i32)
    )

# packet id: 76


async def mainMenuIcon() -> bytes:
    return await write(
        ServerPacket.MAIN_MENU_ICON,
        ('|'.join(glob.config.menu_icon), osuTypes.string)
    )

# packet id: 80
# NOTE: deprecated


async def monitor() -> bytes:
    # this is an older (now removed) 'anticheat' feature of the osu!
    # client; basically, it would do some checks (most likely for aqn),
    # screenshot your desktop (and send it to osu! servers), then trigger
    # the processlist to be sent to bancho as well (also now unused).

    # this doesn't work on newer clients, and i had no plans
    # of trying to put it to use - just coded for completion.
    return await write(ServerPacket.MONITOR)

# packet id: 81


async def matchPlayerSkipped(pid: int) -> bytes:
    return await write(
        ServerPacket.MATCH_PLAYER_SKIPPED,
        (pid, osuTypes.i32)
    )

# packet id: 83


async def userPresence(p) -> bytes:
    return await write(
        ServerPacket.USER_PRESENCE,
        (p.id, osuTypes.i32),
        (p.name, osuTypes.string),
        (p.utc_offset + 24, osuTypes.u8),
        (p.country[0], osuTypes.u8),
        (p.bancho_priv | (p.status.mode.as_vanilla << 5), osuTypes.u8),
        (p.location[0], osuTypes.f32),  # long
        (p.location[1], osuTypes.f32),  # lat
        (p.gm_stats.rank, osuTypes.i32)
    ) if p.id != 1 else (  # default for bot
        b'S\x00\x00\x19\x00\x00\x00\x01\x00\x00\x00'
        b'\x0b\x04Aika\x14&\x1f\x00\x00\x9d\xc2\x00'
        b'\x000B\x00\x00\x00\x00'
    )

# packet id: 86


async def restartServer(ms: int) -> bytes:
    return await write(
        ServerPacket.RESTART,
        (ms, osuTypes.i32)
    )

# packet id: 88


async def matchInvite(p, t_name: str) -> bytes:
    msg = f'Come join my game: {p.match.embed}.'
    return await write(
        ServerPacket.MATCH_INVITE,
        ((p.name, msg, t_name, p.id), osuTypes.message)
    )

# packet id: 89


async def channelInfoEnd() -> bytes:
    return await write(ServerPacket.CHANNEL_INFO_END)

# packet id: 91


async def matchChangePassword(new: str) -> bytes:
    return await write(
        ServerPacket.MATCH_CHANGE_PASSWORD,
        (new, osuTypes.string)
    )

# packet id: 92


async def silenceEnd(delta: int) -> bytes:
    return await write(
        ServerPacket.SILENCE_END,
        (delta, osuTypes.i32)
    )

# packet id: 94


async def userSilenced(pid: int) -> bytes:
    return await write(
        ServerPacket.USER_SILENCED,
        (pid, osuTypes.i32)
    )

""" not sure why 95 & 96 exist? unused in gulag """

# packet id: 95


async def userPresenceSingle(pid: int) -> bytes:
    return await write(
        ServerPacket.USER_PRESENCE_SINGLE,
        (pid, osuTypes.i32)
    )

# packet id: 96


async def userPresenceBundle(pid_list: list[int]) -> bytes:
    return await write(
        ServerPacket.USER_PRESENCE_BUNDLE,
        (pid_list, osuTypes.i32_list)
    )

# packet id: 100


async def userDMBlocked(target: str) -> bytes:
    return await write(
        ServerPacket.USER_DM_BLOCKED,
        (('', '', target, 0), osuTypes.message)
    )

# packet id: 101


async def targetSilenced(target: str) -> bytes:
    return await write(
        ServerPacket.TARGET_IS_SILENCED,
        (('', '', target, 0), osuTypes.message)
    )

# packet id: 102


async def versionUpdateForced() -> bytes:
    return await write(ServerPacket.VERSION_UPDATE_FORCED)

# packet id: 103


async def switchServer(t: int) -> bytes:  # (idletime < t || match != null)
    return await write(
        ServerPacket.SWITCH_SERVER,
        (t, osuTypes.i32)
    )

# packet id: 104


async def accountRestricted() -> bytes:
    return await write(ServerPacket.ACCOUNT_RESTRICTED)

# packet id: 105
# NOTE: deprecated


async def RTX(msg: str) -> bytes:
    # bit of a weird one, sends a request to the client
    # to show some visual effects on screen for 5 seconds:
    # - black screen, freezes game, beeps loudly.
    # within the next 3-8 seconds at random.
    return await write(
        ServerPacket.RTX,
        (msg, osuTypes.string)
    )

# packet id: 106


async def matchAbort() -> bytes:
    return await write(ServerPacket.MATCH_ABORT)

# packet id: 107


async def switchTournamentServer(ip: str) -> bytes:
    # the client only reads the string if it's
    # not on the client's normal endpoints,
    # but we can send it either way xd.
    return await write(
        ServerPacket.SWITCH_TOURNAMENT_SERVER,
        (ip, osuTypes.string)
    )
