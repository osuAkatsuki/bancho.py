# -*- coding: utf-8 -*-

from typing import Any, Tuple, Dict, Union
from enum import IntEnum
import struct

from objects import glob
from objects.player import Player
from objects.web import Request
from constants.mods import Mods
from constants.types import ctypes
from console import printlog, Ansi

PacketParam = Tuple[Any, ctypes]
Specifiers = Dict[ctypes, str]
Slice = Union[int, slice]

class BinaryArray:
    def __init__(self) -> None:
        self._data = bytearray()

    # idk if required along with __getitem__
    def __bytes__(self) -> bytes:
        return bytes(self._data)

    def __iadd__(self, other: Union[bytes, bytearray, int]) -> None:
        #if not isinstance(other, (bytes, bytearray)):
        #    raise Exception('HOW')
        self._data.extend(other)
        return self

    def __getitem__(self, key: Slice) -> Union[bytearray, int]:
        #in the unsafe speedy mood
        return self._data[key]

    def __setitem__(self, key: Slice,
                    value: Union[int, Tuple[int], bytearray]) -> None:
        self._data[key] = value

    def __len__(self) -> int:
        return len(self._data)

class PacketReader:
    def __init__(self, data): # take request body in bytes form as param
        self._data = bytearray(data)
        self._offset = 0

        self.packetID = 0
        self.length = 0

        self.specifiers: Final[Specifiers] = {
            ctypes.i8:  'b', # good
            ctypes.u8:  'B',  # time
            ctypes.i16: 'h',   # to
            ctypes.u16: 'H',    # ask
            ctypes.i32: 'i',     # my self
            ctypes.u32: 'I',      # why im
            ctypes.f32: 'f',       # alive
            ctypes.i64: 'q',        # B)
            ctypes.u64: 'Q',
            ctypes.f64: 'd'
        }

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

    def read_packet_header(self) -> Tuple[int]:
        if len(self.data) < 7:
            # packet is invalid, end connection
            self.packetID = -1
            self._offset += len(self.data)
            printlog(f'[ERR] Data misread! (len: {len(self.data)})', Ansi.LIGHT_RED)
            return

        self.packetID, self.length = struct.unpack('<HxI', self.data[:7])
        self._offset += 7 # Read our first 7 bytes for packetid & len

    def read(self, *types) -> Tuple[Any]:
        ret = []
        for t in types:
            if t == ctypes.string:
                self._offset += 1
                if self._data[self._offset - 1] == 0x00:
                    continue # empty string

                length = self.read_uleb128()
                ret.append(self.data[:length].decode())
                self._offset += length
            elif t == ctypes.i32_list:
                # read length
                length = struct.unpack('<h', self.data[:2])[0]
                self._offset += 2

                # TODO: test speeds?
                #ret.extend(struct.unpack('<i', self.data[:i]) for i in range(length, step = 4))
                #self._offset += length // 4

                for _ in range(length):
                    ret.append(struct.unpack('<i', self.data[:4]))
                    self._offset += 4
            else:
                fmt = self.specifiers[t]
                size = struct.calcsize(fmt)
                ret.extend(struct.unpack(fmt, self.data[:size]))
                self._offset += size
        return ret

    def read_uleb128(self) -> int:
        val = shift = 0

        while True:
            b = self._data[self._offset]
            self._offset += 1

            val = val | ((b & 0b01111111) << shift)
            if (b & 0b10000000) == 0x00: break
            shift += 7

        return val

# TODO: maybe inherit bytearray?
class PacketStream:
    def __init__(self) -> None:
        self.headers = [ # Tuple so we can add to it.
            'HTTP/1.0 200 OK',
            # Content-Length is added upon building on the
            # final packet data, this way we can ensure it's
            # positions - the osu! client does NOT like it
            # being out of place.
        ]
        self._data = BinaryArray()

    def add_header(self, header: str) -> None:
        self.headers.append(header)

    def __bytes__(self) -> bytes:
        self.headers.insert(1, f'Content-Length: {len(self._data)}')
        self.headers.append('\r\n') # Delimit for body
        return '\r\n'.join(self.headers).encode('utf-8', 'strict') + bytes(self._data)

    def __iadd__(self, other: Union[bytes, bytearray, int]) -> None:
        self._data += other
        return self

    def __getitem__(self, key: Slice) -> Union[bytearray, int]:
        return self._data[key]

    def __setitem__(self, key: Slice,
                    value: Union[int, Tuple[int], bytearray]) -> None:
        self._data[key] = value

    def __len__(self) -> int:
        return len(self._data)

    def empty(self) -> bool:
        return len(self._data) == 0

def write_uleb128(num: int) -> bytearray:
    if num == 0:
        return bytearray(b'\x00')

    arr = bytearray()
    length = 0

    while num > 0:
        arr.append(num & 127)
        num >>= 7
        if num != 0:
            arr[length] |= 128
        length += 1

    return arr

def write(id: int, *args: Tuple[PacketParam]) -> bytes:
    ret = bytearray()

    ret.extend(struct.pack('<Hx', id))
    st_ptr = len(ret)

    for param, param_type in args:
        if param_type == ctypes.raw: # bytes, just add to self.data
            ret.extend(param)
        elif param_type == ctypes.string:
            if (length := len(param)) == 0:
                # Empty string
                ret.append(0)
                continue

            # String has content.
            ret.append(11)
            ret.extend(write_uleb128(length))
            ret.extend(param.encode('utf-8', 'replace'))
        elif param_type == ctypes.i32_list:
            length = len(param)
            ret.extend(struct.pack('<h', (length * 4) + 2))

            for _ in range(length):
                ret.append(struct.unpack('<i', param))
        else: # use struct
            ret.extend(
                struct.pack('<' + {
                ctypes.i8:  'b',
                ctypes.u8:  'B',
                ctypes.i16: 'h',
                ctypes.u16: 'H',
                ctypes.i32: 'i',
                ctypes.u32: 'I',
                ctypes.f32: 'f',
                ctypes.i64: 'q',
                ctypes.u64: 'Q',
                ctypes.f64: 'd'
            }[param_type], param))

    # Add size
    ret[st_ptr:st_ptr] = struct.pack('<I', len(ret) - st_ptr)
    return ret

class Packet(IntEnum):
    # Both server & client packetIDs
    c_changeAction = 0 # status update
    c_sendPublicMessage = 1
    c_logout = 2
    c_requestStatusUpdate = 3 # request
    c_ping = 4
    s_userID = 5
    s_sendMessage = 7
    s_Pong = 8
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
    s_matchJoinSuccess = 36
    s_matchJoinFail = 37
    c_matchChangeSlot = 38
    c_matchReady = 39
    c_matchLock = 40
    c_matchChangeSettings = 41
    s_fellowSpectatorJoined = 42
    s_fellowSpectatorLeft = 43
    c_matchStart = 44
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
def loginResponse(id) -> bytes:
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
        (id, ctypes.i32)
    )

# PacketID: 7
def sendMessage(client: str, msg: str, target: str,
                client_id: int) -> bytes:
    return write(
        Packet.s_sendMessage,
        (client, ctypes.string),
        (msg, ctypes.string),
        (target, ctypes.string),
        (client_id, ctypes.i32)
    )

# PacketID: 8
def pong() -> bytes:
    return write(Packet.s_Pong)

# PacketID: 11
def userStats(p: Player) -> bytes:
    return write(
        Packet.s_userStats,
        (p.id, ctypes.i32),
        (p.status.action, ctypes.i8),
        (p.status.info_text, ctypes.string),
        (p.status.beatmap_md5, ctypes.string),
        (p.status.mods, ctypes.i32),
        (p.status.game_mode, ctypes.i8),
        (p.status.beatmap_id, ctypes.i32),
        (p.gm_stats.rscore, ctypes.i64),
        (p.gm_stats.acc, ctypes.f32),
        (p.gm_stats.playcount, ctypes.i32),
        (p.gm_stats.tscore, ctypes.i64),
        (p.gm_stats.rank, ctypes.i32),
        (p.gm_stats.pp, ctypes.i16)) if p.id != 1 else \
        b'\x10' # TODO: raw bytes for aika

# PacketID: 12
def logout(userID: int) -> bytes:
    return write(
        Packet.s_userLogout,
        (userID, ctypes.i32),
        (0, ctypes.i8)
    )

# PacketID: 24
def notification(notif: str) -> bytes:
    return write(Packet.s_notification, (notif, ctypes.string))

# PacketID: 64
def channelJoin(chan: str) -> bytes:
    return write(
        Packet.s_channelJoinSuccess,
        (chan, ctypes.string)
    )

# PacketID: 65
def channelInfo(name: str, topic: str, p_count: int) -> bytes:
    return write(
        Packet.s_channelInfo,
        (name, ctypes.string),
        (topic, ctypes.string),
        (p_count, ctypes.i16)
    )

# PacketID: 71
def banchoPrivileges(priv: int) -> bytes:
    return write(
        Packet.s_supporterGMT,
        (priv, ctypes.i32)
    )

# PacketID: 75
def protocolVersion(num: int) -> bytes:
    return write(
        Packet.s_protocolVersion,
        (num, ctypes.i32)
    )

# PacketID: 76
def mainMenuIcon(**urls) -> bytes:
    return write(
        Packet.s_mainMenuIcon,
        ('|'.join([
            'https://akatsuki.pw/static/logos/logo_ingame.png',
            'https://akatsuki.pw'
        ]), ctypes.string
        )
    )

# PacketID: 83
def userPresence(p: Player) -> bytes:
    return write(
        Packet.s_userPresence,
        (p.id, ctypes.i32),
        (p.name, ctypes.string),
        (p.utc_offset, ctypes.i8),
        (p.country, ctypes.i8), # break break
        (p.bancho_priv, ctypes.i8),
        (0.0, ctypes.f32), # lat
        (0.0, ctypes.f32), # long
        (p.gm_stats.rank, ctypes.i32)
    )

# PacketID: 86
def restartServer(ms: int) -> bytes:
    return write(
        Packet.s_restart,
        (ms, ctypes.i32)
    )

# PacketID: 89
def channelinfoEnd() -> bytes:
    return write(Packet.s_channelInfoEnd)

# PacketID: 105
def RTX(notif: str) -> bytes:
    return write(Packet.s_RTX, (notif, ctypes.string))
