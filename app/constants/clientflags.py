from __future__ import annotations

from enum import IntFlag
from enum import unique

from app.utils import escape_enum
from app.utils import pymysql_encode

__all__ = ("ClientFlags",)


@unique
@pymysql_encode(escape_enum)
class ClientFlags(IntFlag):
    """osu! anticheat <= 2016 (unsure of age)"""

    # NOTE: many of these flags are quite outdated and/or
    # broken and are even known to false positive quite often.
    # they can be helpful; just take them with a grain of salt.

    CLEAN = 0  # no flags sent

    # flags for timing errors or desync.
    SPEED_HACK_DETECTED = 1 << 1

    # this is to be ignored by server implementations. osu! team trolling hard
    INCORRECT_MOD_VALUE = 1 << 2

    MULTIPLE_OSU_CLIENTS = 1 << 3
    CHECKSUM_FAILURE = 1 << 4
    FLASHLIGHT_CHECKSUM_INCORRECT = 1 << 5

    # these are only used on the osu!bancho official server.
    OSU_EXECUTABLE_CHECKSUM = 1 << 6
    MISSING_PROCESSES_IN_LIST = 1 << 7  # also deprecated as of 2018

    # flags for either:
    # 1. pixels that should be outside the visible radius
    # (and thus black) being brighter than they should be.
    # 2. from an internal alpha value being incorrect.
    FLASHLIGHT_IMAGE_HACK = 1 << 8

    SPINNER_HACK = 1 << 9
    TRANSPARENT_WINDOW = 1 << 10

    # (mania) flags for consistently low press intervals.
    FAST_PRESS = 1 << 11

    # from my experience, pretty decent
    # for detecting autobotted scores.
    RAW_MOUSE_DISCREPANCY = 1 << 12
    RAW_KEYBOARD_DISCREPANCY = 1 << 13


@unique
@pymysql_encode(escape_enum)
class LastFMFlags(IntFlag):
    """osu! anticheat 2019"""

    # XXX: the aqn flags were fixed within hours of the osu!
    # update, and vanilla hq is not so widely used anymore.
    RUN_WITH_LD_FLAG = 1 << 14
    CONSOLE_OPEN = 1 << 15
    EXTRA_THREADS = 1 << 16
    HQ_ASSEMBLY = 1 << 17
    HQ_FILE = 1 << 18
    REGISTRY_EDITS = 1 << 19
    SDL2_LIBRARY = 1 << 20
    OPENSSL_LIBRARY = 1 << 21
    AQN_MENU_SAMPLE = 1 << 22
