from enum import IntEnum, IntFlag, unique

@unique
class Privileges(IntFlag):
    # Design inspired from rumoi/ruri.
    # https://github.com/rumoi/ruri/blob/master/ruri/Source.cpp#L13-L42
    # Spaces left for possible future changes.
    Banned = 0
    Verified = 1 << 0 # Has verified their account
    Visible = 1 << 1 # Can be seen by normal users
    Whitelisted = 1 << 2 # Can bypass basic anticheat measures
    Tournament = 1 << 3 # Is a referee in every match they join.

    Supporter = 1 << 5 # Has tier 1 donor
    Premium = 1 << 6 # Has tier 2 donor

    Nominator = 1 << 9 # Can change the ranked-status of beatmaps.
    Mod = 1 << 10 # Can use basic moderation tools (silence, kick).

    Admin = 1 << 14 # Can access user information, and restrict/ban/etc.
    Dangerous = 1 << 18 # Can access potentially dangerous information

@unique
class BanchoPrivileges(IntFlag):
    Player = 1 << 0
    Moderator = 1 << 1
    Supporter = 1 << 2
    Owner = 1 << 3
    Developer = 1 << 4
    Tournament = 1 << 5

@unique
class Type(IntEnum):
    i8  = 0
    u8  = 1
    i16 = 2
    u16 = 3
    i32 = 4
    u32 = 5
    f32 = 6
    i64 = 7
    u64 = 8
    f64 = 9

    i32_list = 10
    string = 11
    raw = 12

@unique
class Mods(IntEnum):
    NOMOD = 0
    NOFAIL = 1 << 0
    EASY = 1 << 1
    TOUCHSCREEN = 1 << 2
    HIDDEN = 1 << 3
    HARDROCK = 1 << 4
    SUDDENDEATH = 1 << 5
    DOUBLETIME = 1 << 6
    RELAX = 1 << 7
    HALFTIME = 1 << 8
    NIGHTCORE = 1 << 9
    FLASHLIGHT = 1 << 10
    AUTOPLAY = 1 << 11
    SPUNOUT = 1 << 12
    RELAX2 = 1 << 13
    PERFECT = 1 << 14
    KEY4 = 1 << 15
    KEY5 = 1 << 16
    KEY6 = 1 << 17
    KEY7 = 1 << 18
    KEY8 = 1 << 19
    KEYMOD = 1 << 20
    FADEIN = 1 << 21
    RANDOM = 1 << 22
    LASTMOD = 1 << 23
    KEY9 = 1 << 24
    KEY10 = 1 << 25
    KEY1 = 1 << 26
    KEY3 = 1 << 27
    KEY2 = 1 << 28
    SCOREV2 = 1 << 29
