# -*- coding: utf-8 -*-

from typing import Any, Sequence, Tuple, Final
from enum import IntEnum, unique
import struct

from objects import glob
from objects.beatmap import Beatmap, BeatmapInfo, BeatmapInfoRequest
from objects.match import Match, ScoreFrame, SlotStatus
from constants.types import osuTypes
from console import plog, Ansi

# Tuple of some of struct's format specifiers
# for clean access within packet pack/unpack.
_specifiers: Final[Tuple[str, ...]] = (
    'b', 'B', # 8
    'h', 'H', # 16
    'i', 'I', 'f', # 32
    'q', 'Q', 'd'  # 64
)

async def read_uleb128(data: bytearray) -> Tuple[int, int]:
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

async def read_string(data: bytearray) -> Tuple[str, int]:
    """ Read a string (ULEB128 & string) from `data`. """
    offset = 1

    if data[0] == 0x00:
        return '', offset

    length, offs = await read_uleb128(data[offset:])
    offset += offs
    return data[offset:offset+length].decode(), offset + length

async def read_i32_list(data: bytearray, long_len: bool = False
                       ) -> Tuple[Tuple[int, ...], int]:
    """ Read an int32 list from `data`. """
    ret = []
    offs = 4 if long_len else 2
    for _ in range(int.from_bytes(data[:offs], 'little')):
        ret.append(int.from_bytes(data[offs:offs+4], 'little'))
        offs += 4

    return ret, offs

async def read_match(data: bytearray) -> Tuple[Match, int]:
    """ Read an osu! match from `data`. """
    m = Match()

    # Ignore match id (i32) & inprogress (i8).
    offset = 3

    # Read type & match mods.
    m.type, m.mods = struct.unpack('<bI', data[offset:offset+5])
    offset += 5

    # Read match name & password.
    m.name, offs = await read_string(data[offset:])
    offset += offs
    m.passwd, offs = await read_string(data[offset:])
    offset += offs

    # Ignore map's name.
    offset += 1
    if data[offset - 1] == 0x0b:
        offset += sum(await read_uleb128(data[offset:]))

    # Read beatmap information (id & md5).
    map_id = int.from_bytes(data[offset:offset+4], 'little')
    offset += 4

    map_md5, offs = await read_string(data[offset:])
    offset += offs

    # Get beatmap object for map selected.
    m.bmap = await Beatmap.from_md5(map_md5)
    if not m.bmap and map_id != (1 << 32) - 1:
        # If they pick an unsubmitted map,
        # just give them Vivid [Insane] lol.
        vivid_md5 = '1cf5b2c2edfafd055536d2cefcb89c0e'
        m.bmap = await Beatmap.from_md5(vivid_md5)

    # Read slot statuses.
    for s in m.slots:
        s.status = data[offset]
        offset += 1

    # Read slot teams.
    for s in m.slots:
        s.team = data[offset]
        offset += 1

    for s in m.slots:
        if s.status & SlotStatus.has_player:
            # Dont think we need this?
            offset += 4

    # Read match host.
    user_id = int.from_bytes(data[offset:offset+4], 'little')
    m.host = await glob.players.get_by_id(user_id)
    offset += 4

    # Read match mode, match scoring,
    # team type, and freemods.
    m.game_mode = data[offset]
    offset += 1
    m.match_scoring = data[offset]
    offset += 1
    m.team_type = data[offset]
    offset += 1
    m.freemods = data[offset]
    offset += 1

    # If we're in freemods mode,
    # read individual slot mods.
    if m.freemods:
        for s in m.slots:
            s.mods = int.from_bytes(data[offset:offset+4], 'little')
            offset += 4

    # Read the seed from multi.
    # XXX: Used for mania random mod.
    m.seed = int.from_bytes(data[offset:offset+4], 'little')
    return m, offset + 4

async def read_scoreframe(data: bytearray) -> Tuple[ScoreFrame, int]:
    """ Read an osu! scoreframe from `data`. """
    offset = 29
    s = ScoreFrame(*struct.unpack('<iBHHHHHHiHH?BB?', data[:offset]))

    if s.score_v2:
        s.combo_portion, s.bonus_portion = struct.unpack('<ff', data[offset:offset+8])
        offset += 8

    return s, offset

async def read_mapInfoRequest(data: bytearray) -> Tuple[Beatmap, int]:
    """ Read an osu! beatmapInfoRequest from `data`. """
    fnames = ids = []

    # Read filenames
    offset = 4
    for _ in range(int.from_bytes(data[:offset], 'little')): # filenames
        fname, offs = await read_string(data[offset:])
        offset += offs
        fnames.append(fname)

    # Read ids
    ids, offs = await read_i32_list(data[offset:], long_len=True)
    return BeatmapInfoRequest(fnames, ids), offset + offs

class PacketReader:
    """A class dedicated to reading osu! packets.

    Attributes
    -----------
    _data: :class:`bytearray`
        The entire bytearray including all data.
        XXX: You should use the `data` property if you want
             data starting from the current offset.

    _offset: :class:`int`
        The offset of the reader; bytes behind the offset
        have already been read, bytes ahead are yet to be read.

    packetID: :class:`int`
        The packetID of the current packet being read.
        -1 if no packet has been read, or packet was corrupt.

    length: :class:`int`
        The length (in bytes) of the current packet.

    Properties
    -----------
    data: :class:`bytearray`
        The data starting from the current offset.
    """
    __slots__ = ('_data', '_offset',
                 'packetID', 'length')

    def __init__(self, data): # take request body in bytes form as param
        self._data = bytearray(data)
        self._offset = 0

        self.packetID = -1
        self.length = 0

    def __repr__(self) -> str:
        return f'<id: {self.packetID} | length: {self.length}>'

    @property
    def data(self) -> bytearray:
        return self._data[self._offset:]

    def empty(self) -> bool:
        return self._offset >= len(self._data)

    def ignore(self, count: int) -> None:
        self._offset += count

    def ignore_packet(self) -> None:
        self._offset += self.length

    async def read_packet_header(self) -> None:
        if len(self.data) < 7:
            # Packet not even minimal legnth.
            # End the connection immediately.
            self.packetID = -1
            self._offset += len(self.data)
            await plog(f'[ERR] Data misread! (len: {len(self.data)})', Ansi.LIGHT_RED)
            return

        self.packetID, self.length = struct.unpack('<HxI', self.data[:7])
        self._offset += 7 # Read our first 7 bytes for packetid & len

    async def read(self, *types: Tuple[osuTypes, ...]) -> Tuple[Any, ...]:
        ret = []

        # Iterate through all types to be read.
        for t in types:
            if t == osuTypes.string:
                # Read a string
                data, offs = await read_string(self.data)
                self._offset += offs
                if data is not None:
                    ret.append(data)
            elif t in (osuTypes.i32_list, osuTypes.i32_list4l):
                # Read an i32 list
                _longlen = t == osuTypes.i32_list4l
                data, offs = await read_i32_list(self.data, _longlen)
                self._offset += offs
                if data is not None:
                    ret.extend(data)
            elif t == osuTypes.channel:
                # Read an osu! channel
                for _ in range(2):
                    data, offs = await read_string(self.data)
                    self._offset += offs
                    if data is not None:
                        ret.append(data)
                ret.append(int.from_bytes(self.data[:2], 'little'))
                self._offset += 2
            elif t == osuTypes.message:
                # Read an osu! message
                for _ in range(3):
                    data, offs = await read_string(self.data)
                    self._offset += offs
                    if data is not None:
                        ret.append(data)
                ret.append(int.from_bytes(self.data[:4], 'little'))
                self._offset += 4
            elif t == osuTypes.match:
                # Read an osu! match
                data, offs = await read_match(self.data)
                self._offset += offs
                ret.append(data)
            elif t == osuTypes.scoreframe:
                # Read an osu! scoreframe
                data, offs = await read_scoreframe(self.data)
                self._offset += offs
            elif t == osuTypes.mapInfoRequest:
                # Read an osu! beatmapInfoRequest.
                data, offs = await read_mapInfoRequest(self.data)
                self._offset += offs
                ret.append(data)
            else:
                # Read a normal datatype
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
    if (length := len(s)) == 0:
        return bytearray(b'\x00')

    ret = bytearray()

    # String has content.
    ret.append(11)
    ret.extend(await write_uleb128(length) +
               s.encode())

    return ret

async def write_i32_list(l: Tuple[int, ...]) -> bytearray:
    """ Write `l` into bytes (int32 list). """
    ret = bytearray(struct.pack('<h', len(l)))

    for i in l:
        ret.extend(struct.pack('<i', i))

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

async def write_mapInfoReply(maps: Sequence[BeatmapInfo]) -> bytearray:
    """ Write `maps` into bytes (osu! map info). """
    ret = bytearray(len(maps).to_bytes(4, 'little'))

    # Write files
    for m in maps:
        ret.extend(struct.pack('<hiiiBbbbb',
            m.id, m.map_id, m.set_id, m.thread_id, m.status,
            m.osu_rank, m.fruits_rank, m.taiko_rank, m.mania_rank
        ))
        ret.extend(await write_string(m.map_md5))

    return ret

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
        ret.extend(await write_string('')) # name
        ret.extend(((1 << 32) - 1).to_bytes(4, 'little')) # id
        ret.extend(await write_string('')) # md5

    ret.extend(s.status for s in m.slots)
    ret.extend(s.team for s in m.slots)

    for s in m.slots:
        if s.player:
            ret.extend(s.player.id.to_bytes(4, 'little'))

    ret.extend(m.host.id.to_bytes(4, 'little'))
    ret.extend((
        m.game_mode,
        m.match_scoring,
        m.team_type,
        m.freemods
    ))

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

async def write(packid: int, *args: Tuple[Any, ...]) -> bytes:
    """ Write `args` into bytes. """
    ret = bytearray(struct.pack('Hx', packid))

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
        elif p_type == osuTypes.mapInfoReply:
            ret.extend(await write_mapInfoReply(p))
        else: # use struct
            ret.extend(struct.pack(f'<{_specifiers[p_type]}', p))

    # Add size
    ret[3:3] = struct.pack('<I', len(ret) - 3)
    return ret

@unique
class Packet(IntEnum):
    # Both server & client packetIDs
    # Packets commented out are unused.
    c_changeAction = 0
    c_sendPublicMessage = 1
    c_logout = 2
    c_requestStatusUpdate = 3
    c_ping = 4
    s_userID = 5
    s_sendMessage = 7
    s_Pong = 8
    s_handleIrcChangeUsername = 9
    s_handleIrcQuit = 10
    s_userStats = 11
    s_userLogout = 12
    s_spectatorJoined = 13
    s_spectatorLeft = 14
    s_spectateFrames = 15
    c_startSpectating = 16
    c_stopSpectating = 17
    c_spectateFrames = 18
    s_versionUpdate = 19
    #c_errorReport = 20
    c_cantSpectate = 21
    s_spectatorCantSpectate = 22
    s_getAttention = 23
    s_notification = 24
    c_sendPrivateMessage = 25
    s_updateMatch = 26
    s_newMatch = 27
    s_disposeMatch = 28
    c_partLobby = 29
    c_joinLobby = 30
    c_createMatch = 31
    c_joinMatch = 32
    c_partMatch = 33
    #c_lobbyJoinMatch = 34
    #c_lobbyPartMatch = 35
    s_matchJoinSuccess = 36
    s_matchJoinFail = 37
    c_matchChangeSlot = 38
    c_matchReady = 39
    c_matchLock = 40
    c_matchChangeSettings = 41
    s_fellowSpectatorJoined = 42
    s_fellowSpectatorLeft = 43
    c_matchStart = 44
    s_allPlayerLoaded = 45
    s_matchStart = 46
    c_matchScoreUpdate = 47
    s_matchScoreUpdate = 48
    c_matchComplete = 49
    s_matchTransferHost = 50
    c_matchChangeMods = 51
    c_matchLoadComplete = 52
    s_matchAllPlayersLoaded = 53
    c_matchNoBeatmap = 54
    c_matchNotReady = 55
    c_matchFailed = 56
    s_matchPlayerFailed = 57
    s_matchComplete = 58
    c_matchHasBeatmap = 59
    c_matchSkipRequest = 60
    s_matchSkip = 61
    #s_unauthorized = 62
    c_channelJoin = 63
    s_channelJoinSuccess = 64
    s_channelInfo = 65
    s_channelKicked = 66
    s_channelAutoJoin = 67
    c_beatmapInfoRequest = 68
    s_beatmapInfoReply = 69
    c_matchTransferHost = 70
    s_supporterGMT = 71
    s_friendsList = 72
    c_friendAdd = 73
    c_friendRemove = 74
    s_protocolVersion = 75
    s_mainMenuIcon = 76
    c_matchChangeTeam = 77
    c_channelPart = 78
    c_ReceiveUpdates = 79
    s_monitor = 80
    s_matchPlayerSkipped = 81
    c_setAwayMessage = 82
    s_userPresence = 83
    c_ircOnly = 84
    c_userStatsRequest = 85
    s_restart = 86
    c_matchInvite = 87
    s_invite = 88
    s_channelInfoEnd = 89
    c_matchChangePassword = 90
    s_matchChangePassword = 91
    s_silenceEnd = 92
    c_tournamentMatchInfoRequest = 93
    s_userSilenced = 94
    s_userPresenceSingle = 95
    s_userPresenceBundle = 96
    c_userPresenceRequest = 97
    c_userPresenceRequestAll = 98
    c_userToggleBlockNonFriendPM = 99
    s_userPMBlocked = 100
    s_targetIsSilenced = 101
    s_versionUpdateForced = 102
    s_switchServer = 103
    s_accountRestricted = 104
    s_RTX = 105
    s_matchAbort = 106 # osu labels this as a client packet LOL
    s_switchTournamentServer = 107
    c_tournamentJoinMatchChannel = 108
    c_tournamentLeaveMatchChannel = 109

#
# Packets
#

# PacketID: 5
async def userID(id: int) -> bytes:
    # ID Responses:
    # -1: Authentication Failed
    # -2: Old Client
    # -3: Banned
    # -4: Banned
    # -5: Error occurred
    # -6: Needs supporter
    # -7: Password reset
    # -8: Requires verification
    # ??: Valid ID
    return await write(
        Packet.s_userID,
        (id, osuTypes.i32)
    )

# PacketID: 7
async def sendMessage(client: str, msg: str, target: str,
                      client_id: int) -> bytes:
    return await write(
        Packet.s_sendMessage,
        ((client, msg, target, client_id), osuTypes.message)
    )

# PacketID: 8
async def pong() -> bytes:
    return await write(Packet.s_Pong)

# PacketID: 11
async def userStats(p) -> bytes:
    return await write(
        Packet.s_userStats,
        (p.id, osuTypes.i32),
        (p.status.action, osuTypes.u8),
        (p.status.info_text, osuTypes.string),
        (p.status.map_md5, osuTypes.string),
        (p.status.mods, osuTypes.i32),
        (p.status.game_mode, osuTypes.u8),
        (p.status.map_id, osuTypes.i32),
        (p.gm_stats.rscore, osuTypes.i64),
        (p.gm_stats.acc, osuTypes.f32),
        (p.gm_stats.plays, osuTypes.i32),
        (p.gm_stats.tscore, osuTypes.i64),
        (p.gm_stats.rank, osuTypes.i32),
        (p.gm_stats.pp, osuTypes.i16)
    ) if p.id != 1 else (
        b'\x0b\x00\x00=\x00\x00\x00\x01\x00\x00'
        b'\x00\x08\x0b\x0eout new code..\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x80?'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    )

# PacketID: 12
async def logout(userID: int) -> bytes:
    return await write(
        Packet.s_userLogout,
        (userID, osuTypes.i32),
        (0, osuTypes.u8)
    )

# PacketID: 13
async def spectatorJoined(id: int) -> bytes:
    return await write(Packet.s_spectatorJoined, (id, osuTypes.i32))

# PacketID: 14
async def spectatorLeft(id: int) -> bytes:
    return await write(Packet.s_spectatorLeft, (id, osuTypes.i32))

# PacketID: 15
async def spectateFrames(data: bytearray) -> bytes:
    return ( # a little hacky, but quick.
        Packet.s_spectateFrames.to_bytes(3, 'little', signed=True) +
        len(data).to_bytes(4, 'little') + data
    )

# PacketID: 19
async def versionUpdate() -> bytes:
    return await write(Packet.s_versionUpdate)

# PacketID: 22
async def spectatorCantSpectate(id: int) -> bytes:
    return await write(Packet.s_spectatorCantSpectate, (id, osuTypes.i32))

# PacketID: 23
async def getAttention() -> bytes:
    return await write(Packet.s_getAttention)

# PacketID: 24
async def notification(notif: str) -> bytes:
    return await write(Packet.s_notification, (notif, osuTypes.string))

# PacketID: 26
async def updateMatch(m: Match) -> bytes:
    return await write(Packet.s_updateMatch, (m, osuTypes.match))

# PacketID: 27
async def newMatch(m: Match) -> bytes:
    return await write(Packet.s_newMatch, (m, osuTypes.match))

# PacketID: 28
async def disposeMatch(id: int) -> bytes:
    return await write(Packet.s_disposeMatch, (id, osuTypes.i32))

# PacketID: 36
async def matchJoinSuccess(m: Match) -> bytes:
    return await write(Packet.s_matchJoinSuccess, (m, osuTypes.match))

# PacketID: 37
async def matchJoinFail(m: Match) -> bytes:
    return await write(Packet.s_matchJoinFail)

# PacketID: 42
async def fellowSpectatorJoined(id: int) -> bytes:
    return await write(
        Packet.s_fellowSpectatorJoined,
        (id, osuTypes.i32)
    )

# PacketID: 43
async def fellowSpectatorLeft(id: int) -> bytes:
    return await write(
        Packet.s_fellowSpectatorLeft,
        (id, osuTypes.i32)
    )

# PacketID: 46
async def matchStart(m: Match) -> bytes:
    return await write(
        Packet.s_matchStart,
        (m, osuTypes.match)
    )

# PacketID: 48
async def matchScoreUpdate(frame: ScoreFrame) -> bytes:
    return await write(
        Packet.s_matchScoreUpdate,
        (frame, osuTypes.scoreframe)
    )

# PacketID: 50
async def matchTransferHost() -> bytes:
    return await write(Packet.s_matchTransferHost)

# PacketID: 53
async def matchAllPlayerLoaded() -> bytes:
    return await write(Packet.s_matchAllPlayersLoaded)

# PacketID: 57
async def matchPlayerFailed(slot_id: int) -> bytes:
    return await write(
        Packet.s_matchPlayerFailed,
        (slot_id, osuTypes.i32)
    )

# PacketID: 58
async def matchComplete() -> bytes:
    return await write(Packet.s_matchComplete)

# PacketID: 61
async def matchSkip() -> bytes:
    return await write(Packet.s_matchSkip)

# PacketID: 64
async def channelJoin(name: str) -> bytes:
    return await write(
        Packet.s_channelJoinSuccess,
        (name, osuTypes.string)
    )

# PacketID: 65
async def channelInfo(name: str, topic: str,
                      p_count: int) -> bytes:
    return await write(
        Packet.s_channelInfo,
        ((name, topic, p_count), osuTypes.channel)
    )

# PacketID: 66
async def channelKick(name: str) -> bytes:
    return await write(
        Packet.s_channelKicked,
        (name, osuTypes.string)
    )

# PacketID: 67
async def channelAutoJoin(name: str, topic: str,
                          p_count: int) -> bytes:
    return await write(
        Packet.s_channelAutoJoin,
        ((name, topic, p_count), osuTypes.channel)
    )

# PacketID: 69
async def beatmapInfoReply(maps: Sequence[BeatmapInfo]) -> bytes:
    return await write(
        Packet.s_beatmapInfoReply,
        (maps, osuTypes.mapInfoReply)
    )

# PacketID: 71
async def banchoPrivileges(priv: int) -> bytes:
    return await write(
        Packet.s_supporterGMT,
        (priv, osuTypes.i32)
    )

# PacketID: 72
async def friendsList(*friends) -> bytes:
    return await write(
        Packet.s_friendsList,
        (friends, osuTypes.i32_list)
    )

# PacketID: 75
async def protocolVersion(num: int) -> bytes:
    return await write(
        Packet.s_protocolVersion,
        (num, osuTypes.i32)
    )

# PacketID: 76
async def mainMenuIcon() -> bytes:
    return await write(
        Packet.s_mainMenuIcon,
        ('|'.join(glob.config.menu_icon), osuTypes.string)
    )

# PacketID: 80
async def monitor() -> bytes:
    # This is an older (now removed) 'anticheat' feature of the osu!
    # client; basically, it would do some checks (most likely for aqn)
    # screenshot your desktop (and send it to osu! sevrers), then trigger
    # the processlist to be sent to bancho as well (also now unused).

    # This doesn't work on newer clients, and I had no plans
    # of trying to put it to use - just coded for completion.
    return await write(Packet.s_monitor)

# PacketID: 81
async def matchPlayerSkipped(pid: int) -> bytes:
    return await write(
        Packet.s_matchPlayerSkipped,
        (pid, osuTypes.i32)
    )

# PacketID: 83
async def userPresence(p) -> bytes:
    return await write(
        Packet.s_userPresence,
        (p.id, osuTypes.i32),
        (p.name, osuTypes.string),
        (p.utc_offset + 24, osuTypes.u8),
        (p.country[0], osuTypes.u8),
        (p.bancho_priv | (p.status.game_mode << 5), osuTypes.u8),
        (p.location[0], osuTypes.f32), # long
        (p.location[1], osuTypes.f32), # lat
        (p.gm_stats.rank, osuTypes.i32)
    ) if p.id != 1 else (
        b'S\x00\x00\x19\x00\x00\x00\x01\x00\x00\x00'
        b'\x0b\x04Aika\x14&\x1f\x00\x00\x9d\xc2\x00'
        b'\x000B\x00\x00\x00\x00'
    )

# PacketID: 86
async def restartServer(ms: int) -> bytes:
    return await write(
        Packet.s_restart,
        (ms, osuTypes.i32)
    )

# PacketID: 89
async def channelInfoEnd() -> bytes:
    return await write(Packet.s_channelInfoEnd)

# PacketID: 91
async def matchChangePassword(new: str) -> bytes:
    return await write(
        Packet.s_matchChangePassword,
        (new, osuTypes.string)
    )

# PacketID: 92
async def silenceEnd(delta: int) -> bytes:
    return await write(
        Packet.s_silenceEnd,
        (delta, osuTypes.i32)
    )

# PacketID: 94
async def userSilenced(pid: int) -> bytes:
    return await write(
        Packet.s_userSilenced,
        (pid, osuTypes.i32)
    )

# PacketID: 100
async def userPMBlocked(target: str) -> bytes:
    return await write(
        Packet.s_userPMBlocked,
        (('', '', target, 0), osuTypes.message)
    )

# PacketID: 101
async def targetSilenced(target: str) -> bytes:
    return await write(
        Packet.s_targetIsSilenced,
        (('', '', target, 0), osuTypes.message)
    )

# PacketID: 102
async def versionUpdateForced() -> bytes:
    return await write(Packet.s_versionUpdateForced)

# PacketID: 103
async def switchServer(t: int) -> bytes: # (idletime < t || match != null)
    return await write(
        Packet.s_switchServer,
        (t, osuTypes.i32)
    )

# PacketID: 104
async def accountRestricted() -> bytes:
    return await write(Packet.s_accountRestricted)

# PacketID: 105
async def RTX(notif: str) -> bytes:
    # Bit of a weird one, sends a request to the client
    # to show some visual effects on screen for 5 seconds:
    # - Black screenk, freeze game, beeps loudly.
    # within the next 3-8 seconds at random.
    return await write(
        Packet.s_RTX,
        (notif, osuTypes.string)
    )

# PacketID: 106
async def matchAbort() -> bytes:
    return await write(Packet.s_matchAbort)

# PacketID: 107
async def switchTournamentServer(ip: str) -> bytes:
    # The client only reads the string if it's
    # not on the client's normal endpoints,
    # but we can send it either way xd.
    return await write(
        Packet.s_switchTournamentServer,
        (ip, osuTypes.string)
    )
