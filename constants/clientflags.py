from enum import IntFlag, unique

@unique
class ClientFlags:
    Clean = 0
    SpeedHackDetected = 1 << 1
    IncorrectModValue = 1 << 2
    MultipleOsuClients = 1 << 3
    ChecksumFailure = 1 << 4
    FlashlightChecksumIncorrect = 1 << 5
    OsuExecutableChecksum = 1 << 6 # server-side
    MissingProcessesInList = 1 << 7 # server-side. also unused as of 2018
    FlashLightImageHack = 1 << 8
    SpinnerHack = 1 << 9
    TransparentWindow = 1 << 10
    FastPress = 1 << 11
    RawMouseDiscrepancy = 1 << 12
    RawKeyboardDiscrepancy = 1 << 13
