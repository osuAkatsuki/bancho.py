from typing import Any, Tuple
from enum import IntEnum
import struct

from objects.player import Player
from objects.web import Request
from constants import Type
PacketParam = Tuple[Any, Type]

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
        self.headers.insert(1, f'Content-Length: {len(self.data)}')
        #self.headers.append(f'Content-Length: {len(self.data)}')
        self.headers.append('\r\n') # Break for body

        return '\r\n'.join(self.headers).encode('utf-8', 'strict') + self.data

    @staticmethod
    def uleb128_encode(num: int) -> bytearray:
        """
        Encode an int to uleb128

        :param num: int to encode
        :return: bytearray with encoded number
        """
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
                self.data.extend(self.uleb128_encode(length))
                self.data.extend(_data.encode('utf-8', 'replace'))
            elif _type == Type.i32_list:
                pass
            else: # use struct
                self.data.extend(
                    struct.pack('<' + {
                    Type.i8:  'c',
                    Type.i16: 'h',
                    Type.u16: 'H',
                    Type.i32: 'i',
                    Type.u32: 'I',
                    Type.i64: 'q',
                    Type.u64: 'Q'
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
# Events
#
def statusUpdate(p: Player, req: Request) -> None:
    
    pass
