# -*- coding: utf-8 -*-

from enum import IntFlag
from enum import unique

from utils.misc import pymysql_encode
from utils.misc import escape_enum

__all__ = ('ClientFlags',)

@unique
@pymysql_encode(escape_enum)
class ClientFlags(IntFlag):
    # NOTE: many of these flags are quite outdated and/or
    # broken and are even known to false positive quite often.
    # they can be helpful; just take them with a grain of salt.

    """osu! anticheat <= 2016 (unsure of age)"""
    Clean                       = 0 # no flags sent

    # flags for timing errors or desync.
    SpeedHackDetected           = 1 << 1

    # flags when two internal values mismatch.
    # XXX: this false flags a lot so most code
    # written around the community just ignores
    # this bit; i'll investigate a bit i guess.
    IncorrectModValue           = 1 << 2

    MultipleOsuClients          = 1 << 3
    ChecksumFailure             = 1 << 4
    FlashlightChecksumIncorrect = 1 << 5

    # these are only used on the osu!bancho official server.
    OsuExecutableChecksum       = 1 << 6
    MissingProcessesInList      = 1 << 7 # also deprecated as of 2018

    # flags for either:
    # 1. pixels that should be outside the visible radius
    # (and thus black) being brighter than they should be.
    # 2. from an internal alpha value being incorrect.
    FlashLightImageHack         = 1 << 8

    SpinnerHack                 = 1 << 9
    TransparentWindow           = 1 << 10

    # (mania) flags for consistently low press intervals.
    FastPress                   = 1 << 11

    # from my experience, pretty decent
    # for detecting autobotted scores.
    RawMouseDiscrepancy         = 1 << 12
    RawKeyboardDiscrepancy      = 1 << 13

    """osu! anticheat 2019"""
    # XXX: the aqn flags were fixed within hours of the osu!
    # update, and vanilla hq is not so widely used anymore.
    RunWithLdFlag   = 1 << 14
    ConsoleOpen     = 1 << 15
    ExtraThreads    = 1 << 16
    HQAssembly      = 1 << 17
    HQFile          = 1 << 18
    RegistryEdits   = 1 << 19
    SQL2Library     = 1 << 20
    libeay32Library = 1 << 21
    aqnMenuSample   = 1 << 22
