# -*- coding: utf-8 -*-

from typing import Final
from enum import IntFlag, unique

__all__ = ('ClientFlags',)

@unique
class ClientFlags(IntFlag):
    # osu! anticheat < 2016 (unsure of date?)
    # NOTE: many of these flags are effectively useless
    # and are even known to send false positives!
    Clean:                       Final[int] = 0
    SpeedHackDetected:           Final[int] = 1 << 1
    IncorrectModValue:           Final[int] = 1 << 2 # completely useless flag, sends randomly
    MultipleOsuClients:          Final[int] = 1 << 3
    ChecksumFailure:             Final[int] = 1 << 4
    FlashlightChecksumIncorrect: Final[int] = 1 << 5
    OsuExecutableChecksum:       Final[int] = 1 << 6 # server-side
    MissingProcessesInList:      Final[int] = 1 << 7 # server-side. also unused as of 2018
    FlashLightImageHack:         Final[int] = 1 << 8
    SpinnerHack:                 Final[int] = 1 << 9
    TransparentWindow:           Final[int] = 1 << 10
    FastPress:                   Final[int] = 1 << 11
    RawMouseDiscrepancy:         Final[int] = 1 << 12
    RawKeyboardDiscrepancy:      Final[int] = 1 << 13

    # osu! anticheat 2019
    RunWithLdFlag:   Final[int] = 1 << 14
    ConsoleOpen:     Final[int] = 1 << 15
    ExtraThreads:    Final[int] = 1 << 16
    HQAssembly:      Final[int] = 1 << 17
    HQFile:          Final[int] = 1 << 18
    RegistryEdits:   Final[int] = 1 << 19
    SQL2Library:     Final[int] = 1 << 20
    libeay32Library: Final[int] = 1 << 21
    aqnMenuSample:   Final[int] = 1 << 22
