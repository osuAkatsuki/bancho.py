# -*- coding: utf-8 -*-

from typing import Any, Tuple, Final
from enum import IntEnum, unique
import struct

from objects import glob
from objects.match import Match, ScoreFrame, SlotStatus
from constants.types import osuTypes
from console import printlog, Ansi

_specifiers: Final[Tuple[str, ...]] = (
    'b', 'B', # 8
    'h', 'H', # 16
    'i', 'I', 'f', # 32
    'q', 'Q', 'd'  # 64
)

def read_uleb128(data: bytearray) -> Tuple[int, int]:
    offset = val = shift = 0

    while True:
        b = data[offset]
        offset += 1

        val = val | ((b & 0b01111111) << shift)
        if (b & 0b10000000) == 0x00: break
        shift += 7

    return val, offset

def read_string(data: bytearray) -> Tuple[str, int]:
    offset = 1
    if data[0] == 0x00:
        return '', offset

    length, offs = read_uleb128(data[offset:])
    offset += offs
    return data[offset:offset+length].decode(), offset + length

def read_i32_list(data: bytearray) -> Tuple[Tuple[int, ...], int]:
    ret = []
    offs = 2
    for _ in range(struct.unpack('<h', data[:offs])[0]):
        ret.append(struct.unpack('<i', data[offs:offs+4])[0])
        offs += 4

    return ret, offs

def read_match(data: bytearray) -> Tuple[Match, int]:
    # suuuper fucking TODO: make not shit
    m = Match()
    offset = 3 # Ignore matchID (h), inprogress (b)
    m.type, m.mods = struct.unpack('<bI', data[offset:offset+5])
    offset += 5
    m.name, offs = read_string(data[offset:])
    offset += offs
    m.passwd, offs = read_string(data[offset:])
    offset += offs
    m.map_name, offs = read_string(data[offset:])
    offset += offs
    m.map_id = int.from_bytes(data[offset:offset+4], 'little')
    offset += 4
    m.map_md5, offs = read_string(data[offset:])
    offset += offs

    for s in m.slots:
        s.status = data[offset]
        offset += 1

    for s in m.slots:
        s.team = data[offset]
        offset += 1

    for s in m.slots:
        if s.status & SlotStatus.has_player:
            # Dont think we need this?
            offset += 4

    m.host = glob.players.get_by_id(int.from_bytes(data[offset:offset+4], 'little'))
    offset += 4

    m.game_mode = data[offset]
    offset += 1
    m.match_scoring = data[offset]
    offset += 1
    m.team_type = data[offset]
    offset += 1
    m.freemods = data[offset]
    offset += 1

    if m.freemods:
        for s in m.slots:
            s.mods = int.from_bytes(data[offset:offset+4], 'little')
            offset += 4

    m.seed = int.from_bytes(data[offset:offset+4], 'little')
    return m, offset + 4

def read_scoreframe(data) -> Tuple[ScoreFrame, int]:
    s = ScoreFrame()
    offset = 29
    s.time, s.id, s.num300, s.num100, s.num50, s.num_geki, s.num_katu, \
    s.num_miss, s.total_score, s.max_combo, s.perfect, s.current_hp, \
    s.tag_byte, s.score_v2 = struct.unpack('<iBHHHHHHiHH?BB?', data[:offset])

    if s.score_v2:
        s.combo_portion, s.bonus_portion = struct.unpack('<ff', data[offset:offset+8])
        offset += 8

    return s, offset

class PacketReader:
    __slots__ = ('_data', '_offset', 'packetID', 'length', 'specifiers')

    def __init__(self, data): # take request body in bytes form as param
        self._data = bytearray(data)
        self._offset = 0

        self.packetID = 0
        self.length = 0

    def __repr__(self) -> str:
        return f'<id: {self.packetID} | length: {self.length}>'

    @property # get data w/ offset accounted for
    def data(self) -> bytearray:
        return self._data[self._offset:]

    def empty(self) -> bool:
        return self._offset >= len(self._data)

    def ignore(self, count: int) -> None:
        self._offset += count

    def ignore_packet(self) -> None:
        self._offset += self.length

    def read_packet_header(self) -> None:
        if len(self.data) < 7:
            # packet is invalid, end connection
            self.packetID = -1
            self._offset += len(self.data)
            printlog(f'[ERR] Data misread! (len: {len(self.data)})', Ansi.LIGHT_RED)
            return

        self.packetID, self.length = struct.unpack('<HxI', self.data[:7])
        self._offset += 7 # Read our first 7 bytes for packetid & len

    def read(self, *types: Tuple[int, ...]) -> Tuple[Any, ...]:
        ret = []
        for t in types:
            if t == osuTypes.string:
                data, offs = read_string(self.data)
                self._offset += offs
                if data is not None:
                    ret.append(data)
            elif t == osuTypes.i32_list:
                data, offs = read_i32_list(self.data)
                self._offset += offs
                if data is not None:
                    ret.extend(data)
            elif t == osuTypes.channel:
                for _ in range(2):
                    data, offs = read_string(self.data)
                    self._offset += offs
                    if data is not None:
                        ret.append(data)
                ret.append(int.from_bytes(self.data[:2], 'little'))
                self._offset += 2
            elif t == osuTypes.message:
                for _ in range(3):
                    data, offs = read_string(self.data)
                    self._offset += offs
                    if data is not None:
                        ret.append(data)
                ret.append(int.from_bytes(self.data[:4], 'little'))
                self._offset += 4
            elif t == osuTypes.match:
                data, offs = read_match(self.data)
                self._offset += offs
                ret.append(data)
            elif t == osuTypes.scoreframe:
                data, offs = read_scoreframe(self.data)
                self._offset += offs
            else:
                fmt = _specifiers[t]
                size = struct.calcsize(fmt)
                ret.extend(struct.unpack(fmt, self.data[:size]))
                self._offset += size
        return ret

def write_uleb128(num: int) -> bytearray:
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
    if (length := len(s)) == 0:
        return bytearray(b'\x00')

    ret = bytearray()

    # String has content.
    ret.append(11)
    ret.extend(write_uleb128(length))
    ret.extend(s.encode('utf-8', 'replace'))
    return ret

def write_i32_list(l: Tuple[int, ...]) -> bytearray:
    ret = bytearray(struct.pack('<h', len(l)))

    for i in l:
        ret.extend(struct.pack('<i', i))

    return ret

def write_message(client: str, msg: str, target: str,
                  client_id: int) -> bytearray:
    ret = bytearray()
    ret.extend(write_string(client))
    ret.extend(write_string(msg))
    ret.extend(write_string(target))
    ret.extend(struct.pack('<i', client_id))
    return ret

def write_channel(name: str, topic: str,
                  count: int) -> bytearray:
    ret = bytearray()
    ret.extend(write_string(name))
    ret.extend(write_string(topic))
    ret.extend(struct.pack('<h', count))
    return ret

def write_scoreframe(s: ScoreFrame) -> bytearray:
    return bytearray(
        struct.pack(
            '<ibHHHHHHIIbbbb', s.time, s.id, s.num300, s.num100, s.num50,
            s.num_geki, s.num_katu, s.num_miss, s.total_score, s.max_combo,
            s.perfect, s.current_hp, s.tag_byte, s.score_v2
        )
    )

def write_match(m: Match) -> bytearray:
    ret = bytearray()
    ret.extend(struct.pack('<HbbI', m.id, m.in_progress, m.type, m.mods))
    ret.extend(write_string(m.name))
    ret.extend(write_string(m.passwd))
    ret.extend(write_string(m.map_name))
    ret.extend(m.map_id.to_bytes(4, 'little'))
    ret.extend(write_string(m.map_md5))

    ret.extend(s.status for s in m.slots)
    ret.extend(s.team for s in m.slots)

    for s in m.slots:
        if s.player:
            ret.extend(s.player.id.to_bytes(4, 'little'))

    ret.extend(m.host.id.to_bytes(4, 'little'))
    ret.extend([ # bytes
        m.game_mode,
        m.match_scoring,
        m.team_type,
        m.freemods
    ])

    if m.freemods:
        for s in m.slots:
            ret.extend(s.mods.to_bytes(4, 'little'))

    ret.extend(m.seed.to_bytes(4, 'little'))
    return ret

def write(id: int, *args: Tuple[Any, ...]) -> bytes:
    ret = bytearray()

    ret.extend(struct.pack('<Hx', id))

    for param, param_type in args:
        if param_type == osuTypes.raw:
            ret.extend(param)
        elif param_type == osuTypes.string:
            ret.extend(write_string(param))
        elif param_type == osuTypes.i32_list:
            ret.extend(write_i32_list(param))
        elif param_type == osuTypes.message:
            ret.extend(write_message(*param))
        elif param_type == osuTypes.channel:
            ret.extend(write_channel(*param))
        elif param_type == osuTypes.match:
            ret.extend(write_match(param))
        elif param_type == osuTypes.scoreframe:
            ret.extend(write_scoreframe(param))
        else: # use struct
            ret.extend(struct.pack('<' + _specifiers[param_type], param))

    # Add size
    ret[3:3] = struct.pack('<I', len(ret) - 3)
    return ret

@unique
class Packet(IntEnum):
    # Both server & client packetIDs
    # Packets commented out are unused.
    c_changeAction = 0 # status update
    c_sendPublicMessage = 1
    c_logout = 2
    c_requestStatusUpdate = 3 # request
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
    c_errorReport = 20
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
    # unused
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
    c_invite = 87
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
    s_matchAbort = 106
    s_switchTournamentServer = 107
    c_tournamentJoinMatchChannel = 108
    c_tournamentLeaveMatchChannel = 109

#
# Packets
#

# PacketID: 5
def userID(id: int) -> bytes:
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
    return write(
        Packet.s_userID,
        (id, osuTypes.i32)
    )

# PacketID: 7
def sendMessage(client: str, msg: str, target: str,
                client_id: int) -> bytes:
    return write(
        Packet.s_sendMessage,
        ((client, msg, target, client_id), osuTypes.message)
    )

# PacketID: 8
def pong() -> bytes:
    return write(Packet.s_Pong)

# PacketID: 11
def userStats(p) -> bytes:
    return write(
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
        (p.gm_stats.playcount, osuTypes.i32),
        (p.gm_stats.tscore, osuTypes.i64),
        (p.gm_stats.rank, osuTypes.i32),
        (p.gm_stats.pp, osuTypes.i16)
    ) if p.id != 1 else \
        b'\x0b\x00\x00=\x00\x00\x00\x01\x00\x00' \
        b'\x00\x08\x0b\x0eout new code..\x00\x00' \
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' \
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x80?' \
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00' \
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00'

# PacketID: 12
def logout(userID: int) -> bytes:
    return write(
        Packet.s_userLogout,
        (userID, osuTypes.i32),
        (0, osuTypes.u8)
    )

# PacketID: 13
def spectatorJoined(id: int) -> bytes:
    return write(Packet.s_spectatorJoined, (id, osuTypes.i32))

# PacketID: 14
def spectatorLeft(id: int) -> bytes:
    return write(Packet.s_spectatorLeft, (id, osuTypes.i32))

# PacketID: 15
def spectateFrames(data: bytearray) -> bytes:
    # TODO: speedtest
    return write(Packet.s_spectateFrames, (data, osuTypes.raw))
    #return chr(Packet.s_spectateFrames).encode() + bytes(data)

# PacketID: 19
def versionUpdate() -> bytes:
    return write(Packet.s_versionUpdate)

# PacketID: 22
def spectatorCantSpectate(id: int) -> bytes:
    return write(Packet.s_spectatorCantSpectate, (id, osuTypes.i32))

# PacketID: 23
def getAttention() -> bytes:
    return write(Packet.s_getAttention)

# PacketID: 24
def notification(notif: str) -> bytes:
    return write(Packet.s_notification, (notif, osuTypes.string))

# PacketID: 26
def updateMatch(m: Match) -> bytes:
    return write(Packet.s_updateMatch, (m, osuTypes.match))

# PacketID: 27
def newMatch(m: Match) -> bytes:
    return write(Packet.s_newMatch, (m, osuTypes.match))

# PacketID: 28
def disposeMatch(id: int) -> bytes:
    return write(Packet.s_disposeMatch, (id, osuTypes.i32))

# PacketID: 36
def matchJoinSuccess(m: Match) -> bytes:
    return write(Packet.s_matchJoinSuccess, (m, osuTypes.match))

# PacketID: 37
def matchJoinFail(m: Match) -> bytes:
    return write(Packet.s_matchJoinFail)

# PacketID: 42
def fellowSpectatorJoined(id: int) -> bytes:
    return write(Packet.s_fellowSpectatorJoined, (id, osuTypes.i32))

# PacketID: 43
def fellowSpectatorLeft(id: int) -> bytes:
    return write(Packet.s_fellowSpectatorLeft, (id, osuTypes.i32))

# PacketID: 46
def matchStart(m: Match) -> bytes:
    return write(Packet.s_matchStart, (m, osuTypes.match))

# PacketID: 48
def matchScoreUpdate(frame: ScoreFrame) -> bytes:
    return write(Packet.s_matchScoreUpdate, (frame, osuTypes.scoreframe))

# PacketID: 50
def matchTransferHost() -> bytes:
    return write(Packet.s_matchTransferHost)

# PacketID: 53
def matchAllPlayerLoaded() -> bytes:
    return write(Packet.s_matchAllPlayersLoaded)

# PacketID: 57
def matchPlayerFailed(id: int) -> bytes:
    return write(Packet.s_matchPlayerFailed, (id, osuTypes.i32))

# PacketID: 58
def matchComplete() -> bytes:
    return write(Packet.s_matchComplete)

# PacketID: 61
def matchSkip() -> bytes:
    return write(Packet.s_matchSkip)

# PacketID: 64
def channelJoin(name: str) -> bytes:
    return write(Packet.s_channelJoinSuccess, (name, osuTypes.string))

# PacketID: 65
def channelInfo(name: str, topic: str,
                p_count: int) -> bytes:
    return write(
        Packet.s_channelInfo,
        ((name, topic, p_count), osuTypes.channel)
    )

# PacketID: 66
def channelKick(name: str) -> bytes:
    return write(Packet.s_channelKicked, (name, osuTypes.string))

# PacketID: 67
def channelAutoJoin(name: str, topic: str,
                    p_count: int) -> bytes:
    return write(
        Packet.s_channelAutoJoin,
        ((name, topic, p_count), osuTypes.channel)
    )

# PacketID: 69 TODO - beatmapinforeply [i32 len, ]
# i32 length
# length * beatmapinfo struct:
# i16: id
# i32: beatmapid
# i32: beatmapsetid
# i32: threadid
# byte: ranked
# i8: osu rank
# i8: fruits rank # nice job peppy.. does not follow mode id..
# i8: taiko rank
# i8: mania rank
# str: checksum

# PacketID: 71
def banchoPrivileges(priv: int) -> bytes:
    return write(
        Packet.s_supporterGMT,
        (priv, osuTypes.i32)
    )

# PacketID: 72
def friendsList(*friends) -> bytes:
    return write(
        Packet.s_friendsList,
        (friends, osuTypes.i32_list)
    )

# PacketID: 75
def protocolVersion(num: int) -> bytes:
    return write(
        Packet.s_protocolVersion,
        (num, osuTypes.i32)
    )

# PacketID: 76
def mainMenuIcon() -> bytes:
    # TODO: unhardcode lol
    return write(
        Packet.s_mainMenuIcon,
        ('|'.join([
            'https://akatsuki.pw/static/logos/logo_ingame.png',
            'https://akatsuki.pw'
        ]), osuTypes.string
        )
    )

# PacketID: 80
def monitor() -> bytes:
    # This is a little 'anticheat' feature from ppy himself..
    # basically, it would do some checks (most likely for aqn)
    # screenshot your desktop (and send it to osu! sevrers),
    # then trigger the processlist to be sent to bancho as well.

    # This doesn't work on newer clients (and i have), it was
    # no plan on trying to use it, just coded for completion.
    return write(Packet.s_monitor)

# PacketID: 81
def matchPlayerSkipped(id: int) -> bytes:
    return write(Packet.s_matchPlayerSkipped, (id, osuTypes.i32))

# PacketID: 83
def userPresence(p) -> bytes:
    return write(
        Packet.s_userPresence,
        (p.id, osuTypes.i32),
        (p.name, osuTypes.string),
        (p.utc_offset + 24, osuTypes.u8),
        (p.country[0], osuTypes.u8),
        (p.bancho_priv | (p.status.game_mode << 5), osuTypes.u8),
        (p.location[0], osuTypes.f32), # lat
        (p.location[1], osuTypes.f32), # long
        (p.gm_stats.rank, osuTypes.i32)
    ) if p.id != 1 else \
        b'S\x00\x00\x19\x00\x00\x00\x01\x00\x00\x00' \
        b'\x0b\x04Aika\x14&\x1f\x00\x00\x9d\xc2\x00' \
        b'\x000B\x00\x00\x00\x00'

# PacketID: 86
def restartServer(ms: int) -> bytes:
    return write(
        Packet.s_restart,
        (ms, osuTypes.i32)
    )

# PacketID: 89
def channelInfoEnd() -> bytes:
    return write(Packet.s_channelInfoEnd)

# PacketID: 91
def matchChangePassword(new: str) -> bytes:
    return write(Packet.s_matchChangePassword, (new, osuTypes.string))

# PacketID: 92
def silenceEnd(delta: int) -> bytes:
    return write(Packet.s_silenceEnd, (delta, osuTypes.i32))

# PacketID: 94
def userSilenced(id: int) -> bytes:
    return write(Packet.s_userSilenced, (id, osuTypes.i32))

# PacketID: 100
def userPMBlocked(target: str) -> bytes:
    return write(
        Packet.s_userPMBlocked,
        (('', '', target, 0), osuTypes.message)
    )

# PacketID: 101
def targetSilenced(target: str) -> bytes:
    return write(
        Packet.s_targetIsSilenced,
        (('', '', target, 0), osuTypes.message)
    )

# PacketID: 102
def versionUpdateForced() -> bytes:
    return write(Packet.s_versionUpdateForced)

# PacketID: 103
def switchServer(t: int) -> bytes: # (idletime < t || match != null)
    return write(Packet.s_switchServer, (t, osuTypes.i32))

# PacketID: 105
def RTX(notif: str) -> bytes:
    # Sends a request to the client to show notif
    # as a popup, black screen, freeze game and
    # make a beep noise (freezes client) for 5
    # seconds randomly within the next 3-8 seconds.
    return write(Packet.s_RTX, (notif, osuTypes.string))

# PacketID: 106
def matchAbort() -> bytes:
    return write(Packet.s_matchAbort)

# PacketID: 107
def switchTournamentServer(ip: str) -> bytes:
    # The client only reads the string if it's
    # not on the client's normal endpoints,
    # but we can send it either way xd.
    return write(Packet.s_switchTournamentServer, (ip, osuTypes.string))
