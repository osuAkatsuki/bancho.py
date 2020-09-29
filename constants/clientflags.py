# -*- coding: utf-8 -*-

from enum import IntFlag, unique

__all__ = 'ClientFlags',

@unique
class ClientFlags(IntFlag):
    # osu! anticheat < 2016 (unsure of date?)
    # NOTE: many of these flags are effectively useless
    # and are even known to send false positives!
    Clean                       = 0
    SpeedHackDetected           = 1 << 1
    IncorrectModValue           = 1 << 2 # completely useless flag, sends randomly
    MultipleOsuClients          = 1 << 3
    ChecksumFailure             = 1 << 4
    FlashlightChecksumIncorrect = 1 << 5
    OsuExecutableChecksum       = 1 << 6 # server-side
    MissingProcessesInList      = 1 << 7 # server-side. also unused as of 2018
    FlashLightImageHack         = 1 << 8
    SpinnerHack                 = 1 << 9
    TransparentWindow           = 1 << 10
    FastPress                   = 1 << 11
    RawMouseDiscrepancy         = 1 << 12
    RawKeyboardDiscrepancy      = 1 << 13

    # osu! anticheat 2019
    RunWithLdFlag   = 1 << 14
    ConsoleOpen     = 1 << 15
    ExtraThreads    = 1 << 16
    HQAssembly      = 1 << 17
    HQFile          = 1 << 18
    RegistryEdits   = 1 << 19
    SQL2Library     = 1 << 20
    libeay32Library = 1 << 21
    aqnMenuSample   = 1 << 22
