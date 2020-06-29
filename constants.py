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

    Mod = 1 << 9 # Can use basic moderation tools (silence, kick).
    Nominator = 1 << 10 # Can change the ranked-status of beatmaps.

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
    i8 = 0 # even needed?
    i16 = 1
    u16 = 2
    i32 = 3
    u32 = 4
    i64 = 5
    u64 = 6

    i32_list = 8
    string = 10
    raw = 12
