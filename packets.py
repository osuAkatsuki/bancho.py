from typing import Any, Tuple, Dict
from enum import IntEnum
import struct

from objects import glob
from objects.player import Player
from objects.web import Request
from constants import Type, Mods

PacketParam = Tuple[Any, Type]
Specifiers = Dict[Type, str]

class PacketReader:
    def __init__(self, data): # take request body in bytes form as param
        self._data = bytearray(data)
        self._offset = 0

        self.packetID = 0
        self.length = 0

        self.specifiers: Final[Specifiers] = {
            Type.i8:  'b', # good
            Type.u8:  'B',  # time
            Type.i16: 'h',   # to
            Type.u16: 'H',    # ask
            Type.i32: 'i',     # my self
            Type.u32: 'I',      # why im
            Type.f32: 'f',       # alive
            Type.i64: 'q',        # B)
            Type.u64: 'Q',
            Type.f64: 'd'
        }

    @property # get data w/ offset accounted for
    def data(self) -> bytearray:
        return self._data[self._offset:]

    def empty(self) -> bool:
        return self._offset >= len(self._data)

    def ignore(self, count: int) -> None:
        self._offset += count

    def read_packet_header(self) -> Tuple[int]:
        if len(self.data) < 7:
            self.packetID = 0
            self._offset += len(self.data) # end transfer
            print(f'Received garbage data? (len: {len(self.data)})')
            return

        self.packetID, self.length = struct.unpack('<HxI', self.data[:7])
        self._offset += 7 # Read our first 7 bytes for packetid & len

    def read(self, *types) -> Tuple[Any]:
        ret = []
        for t in types:
            if t == Type.string:
                self._offset += 1
                if self._data[self._offset - 1] == 0x00:
                    continue # empty string

                length = self.read_uleb128()
                ret.append(self.data[:length].decode())
                self._offset += length
            elif t == Type.i32_list:
                # read length
                length = struct.unpack('<h', self.data[:2])[0]
                self._offset += 2

                # TODO: test speeds?
                #ret.extend(struct.unpack('<i', self.data[:i]) for i in range(length, step = 4))
                #self._offset += length // 4

                for i in range(0, length, 4):
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

class PacketWriter:
    def __init__(self) -> None:
        self.headers = [
            'HTTP/1.0 200 OK'
            # Content-Length is done on __bytes__()
            # This is required for some custom situations,
            # such as login when we need to add token.
        ]
        self.data = bytearray()

    def __bytes__(self) -> bytes:
        self.headers.insert(1, f'Content-Length: {len(self.data)}') # Must be sent first
        self.headers.append('\r\n') # Break for body

        return '\r\n'.join(self.headers).encode('utf-8', 'strict') + self.data

    @staticmethod
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

    def add_header(self, header: str) -> None:
        self.headers.append(header)

    def write(self, id: int, *args: Tuple[PacketParam]) -> None:
        self.data.extend(struct.pack('<Hx', id))
        st_ptr = len(self.data)

        for _data, _type in args:
            if _type == Type.raw: # bytes, just add to self.data
                self.data += bytearray(_data)
            elif _type == Type.string:
                if (length := len(_data)) == 0:
                    # Empty string
                    self.data.append(0)
                    continue

                # String has content.
                self.data.append(11)
                self.data.extend(self.write_uleb128(length))
                self.data.extend(_data.encode('utf-8', 'replace'))
            elif _type == Type.i32_list:
                pass
            else: # use struct
                self.data.extend(
                    struct.pack('<' + {
                    Type.i8:  'b',
                    Type.u8:  'B',
                    Type.i16: 'h',
                    Type.u16: 'H',
                    Type.i32: 'i',
                    Type.u32: 'I',
                    Type.f32: 'f',
                    Type.i64: 'q',
                    Type.u64: 'Q',
                    Type.f64: 'd'
                }[_type], _data))

        # Add size
        self.data[st_ptr:st_ptr] = struct.pack('<I', len(self.data) - st_ptr)

class Packet(IntEnum):
    # Both server & client packetIDs
    c_changeAction = 0
    c_sendPublicMessage = 1
    c_logout = 2
    c_requestStatusUpdate = 3
    c_pong = 4
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

def userStats(p: Player) -> bytes:
    #update cached stats
    #p.enqueue()#userstats packet

    pw = PacketWriter()

    # status.gamemode will be 0-7 (rx support)
    gm_stats = p.stats[p.status.game_mode]

    if p.id == 2: # Bot
        pw.write(
            Packet.s_userStats,

        )
    pw.write(
        Packet.s_userStats,
        (p.id, Type.u32),
        (p.status.action, Type.i8),
        (p.status.beatmap_md5, Type.string),
        (p.status.mods, Type.i32),
        (p.status.game_mode, Type.i8),
        (p.status.beatmap_id, Type.i32),
        (gm_stats.rscore, Type.u64),
        (gm_stats.acc, Type.f32),
        (gm_stats.playcount, Type.u32),
        (gm_stats.tscore, Type.u64),
        (gm_stats.rank, Type.u32),
        (gm_stats.pp, Type.u16)) # todo: safe with ranked score >32k?

    return bytes(pw.data)

#
# Events
#

def statsUpdateRequest(p: Player, pr: PacketReader) -> None:
    p.enqueue(userStats(p))

def statsRequest(p: Player, pr: PacketReader) -> None:
    if len(pr.data) < 6:
        return

    userIDs = pr.read(Type.i32_list)
    is_online = lambda o: o in glob.players.ids

    for online in filter(is_online, userIDs):
        target = glob.players.get_by_id(online)
        p.enqueue(userStats(target))

def joinChannel(p: Player, pr: PacketReader) -> None:
    if not (chan := pr.read(Type.string)):
        print(f'{p.name} tried to join nonexistant channel {chan}')
        return

    chan = chan[0] # need refactor.. this will be an endless uphill battle

    if (c := glob.channels.get(chan)) and c.join(p):
        print(f'{p.name} joined {chan}.')
        p.channels.append(c)

        # Another much need refactor to stop stuff like this lol
        pw = PacketWriter()
        pw.write(Packet.s_channelJoinSuccess, (c.name, Type.string))
        p.enqueue(bytes(pw.data))
    else:
        print(f'Failed to find channel {chan} that {p.name} attempted to join.')

def statusUpdateRequest(p: Player, pr: PacketReader) -> None:
    #Osu_RequestStatusUpdate
    pass

def readStatus(p: Player, pr: PacketReader) -> None:
    data = pr.read(
        Type.i8, # actionType
        Type.string, # infotext
        Type.string, # beatmap md5
        Type.i32, # mods
        Type.i8, # gamemode
        Type.i32 # beatmapid
    )

    p.status.update(*data) # TODO: probably refactor some status stuff
    p.rx = p.status.mods & Mods.RELAX
    glob.players.broadcast(userStats(p))

def Logout(p: Player, pr: PacketReader) -> None:
    glob.players.remove(p)

    # TODO: logout notif to all players
    #glob.players.broadcast()

    for c in p.channels:
        p.leave_channel(c)

    # stop spectating
    # leave match
    # remove match if only player

    print(f'{p.name} logged out.')
