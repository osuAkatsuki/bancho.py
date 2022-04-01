# like budget wireshark for osu! server stuff
# usage: enable http://localhost:8080 proxy in windows,
#        (https://i.cmyui.xyz/DNnqifKHyBSA9X8NEHg.png)
#        and run this with `mitmdump -qs tools/proxy.py`
from __future__ import annotations

domain = "cmyui.xyz"  # XXX: put your domain here

import re
import struct
import sys
from enum import unique
from enum import IntEnum

from app.logging import RGB
from mitmproxy import http


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


BYTE_ORDER_SUFFIXES = [
    f"{RGB(0x76eb00)!r}B\x1b[0m",
    f"{RGB(0xbfbf00)!r}KB\x1b[0m",
    f"{RGB(0xe98b00)!r}MB\x1b[0m",
    f"{RGB(0xfd4900)!r}GB\x1b[0m",
]


def fmt_bytes(n: int | float) -> str:
    for suffix in BYTE_ORDER_SUFFIXES:
        if n < 1024:
            break
        n /= 1024  # more to go
    return f"{n:,.2f}{suffix}"


DOMAIN_RGX = re.compile(
    rf"^(?P<subdomain>osu|c[e4]?|a|s|b|assets)\.(?:ppy\.sh|{re.escape(domain)})$",
)

PACKET_HEADER_FMT = struct.Struct("<HxI")  # header gives us packet id & data length

print(f"\x1b[0;92mListening (ppy.sh & {domain})\x1b[0m\n")


def response(flow: http.HTTPFlow) -> None:
    if not (r_match := DOMAIN_RGX.match(flow.request.host)):
        return  # unrelated request

    if not (body := flow.response.content):
        return  # empty resp

    sys.stdout.write(f"\x1b[0;93m[{flow.request.method}] {flow.request.url}\x1b[0m\n")
    body_view = memoryview(body)
    body_len = len(body)

    if r_match["subdomain"] in ("c", "ce", "c4", "c5", "c6"):
        if flow.request.method == "POST":
            packet_num = 1
            while body_view:
                # read header
                _pid, plen = PACKET_HEADER_FMT.unpack_from(body_view)
                pid = ServerPackets(_pid)
                body_view = body_view[7:]

                # read data
                pdata = str(body_view[:plen].tobytes())[2:-1]  # remove b''
                body_view = body_view[plen:]

                sys.stdout.write(f"[{packet_num}] \x1b[0;95m{pid!r}\x1b[0m {pdata}\n")

                packet_num += 1

                if packet_num % 5:  # don't build up too much in ram
                    sys.stdout.flush()
        sys.stdout.write("\n")
    else:  # format varies per request
        if (  # todo check host
            (
                # jfif, jpe, jpeg, jpg graphics file
                body_view[:4] == b"\xff\xd8\xff\xe0"
                and body_view[6:11] == b"JFIF\x00"
            )
            or (
                # exif digital jpg
                body_view[:4] == b"\xff\xd8\xff\xe1"
                and body_view[6:11] == b"Exif\x00"
            )
            or (
                # spiff still picture jpg
                body_view[:4] == b"\xff\xd8\xff\xe8"
                and body_view[6:12] == b"SPIFF\x00"
            )
        ):
            sys.stdout.write(f"[{fmt_bytes(body_len)} jpeg file]\n\n")
        elif (
            body_view[:8] == b"\x89PNG\r\n\x1a\n"
            and body_view[-8:] == b"\x49END\xae\x42\x60\x82"
        ):
            sys.stdout.write(f"[{fmt_bytes(body_len)} png file]\n\n")
        elif body_view[:6] in (b"GIF87a", b"GIF89a") and body_view[-2:] == b"\x00\x3b":
            sys.stdout.write(f"[{fmt_bytes(body_len)} gif file]\n\n")
        else:
            sys.stdout.write(f"{str(body)[2:-1]}\n\n")  # remove b''

    sys.stdout.flush()
