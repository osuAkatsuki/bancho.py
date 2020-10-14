# -*- coding: utf-8 -*-

from enum import IntFlag, unique

__all__ = ('ClientFlags',)

@unique
class ClientFlags(IntFlag):
    # NOTE: many of these flags are quite outdated and/or
    # broken and are even known to false positive quite often.
    # they can be helpful; just take them with a grain of salt.

    # osu! anticheat <2016 (unsure of date?)
    Clean                       = 0 # no flags sent
    SpeedHackDetected           = 1 << 1 # basic timewarp detection, can false positive but decent
    IncorrectModValue           = 1 << 2 # this sends almost all the time
    MultipleOsuClients          = 1 << 3
    ChecksumFailure             = 1 << 4
    FlashlightChecksumIncorrect = 1 << 5
    OsuExecutableChecksum       = 1 << 6 # server-side
    MissingProcessesInList      = 1 << 7 # server-side. also unused as of 2018
    FlashLightImageHack         = 1 << 8 # basic enlighten detection
    SpinnerHack                 = 1 << 9
    TransparentWindow           = 1 << 10
    FastPress                   = 1 << 11 # flags for consistent low press intervals,
                                          # decent but not fully conclusive
    RawMouseDiscrepancy         = 1 << 12 # can detect autobotted scores
    RawKeyboardDiscrepancy      = 1 << 13

    # osu! anticheat 2019
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
