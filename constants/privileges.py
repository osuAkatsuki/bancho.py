# -*- coding: utf-8 -*-

from typing import Final
from enum import IntFlag, unique

__all__ = ('Privileges', 'BanchoPrivileges')

@unique
class Privileges(IntFlag):
    """A class to represent user privileges server-side.
    Gaps inbetween groups are left for future changes.
    """

    # A normal vanilla user, access intended for all users.
    # XXX: If a user does not have this bit, they are banned.
    Normal:      Final[int] = 1 << 0

    # Has bypass to low-ceiling anticheat measures (trusted).
    Whitelisted: Final[int] = 1 << 1

    # Donation tiers, receives some extra benefits.
    Supporter:   Final[int] = 1 << 4
    Premium:     Final[int] = 1 << 5

    # Notable users, receives some extra benefits.
    Alumni:      Final[int] = 1 << 7

    # Staff permissions, able to manage server state.
    Tournament:  Final[int] = 1 << 10 # Able to manage match state without host.
    Nominator:   Final[int] = 1 << 11 # Able to manage maps ranked status.
    Mod:         Final[int] = 1 << 12 # Able to manage users (level 1).
    Admin:       Final[int] = 1 << 13 # Able to manage users (level 2).
    Dangerous:   Final[int] = 1 << 14 # Able to manage full server state.

    Staff:       Final[int] = Mod | Admin | Dangerous

@unique
class BanchoPrivileges(IntFlag):
    Player:     Final[int] = 1 << 0
    Moderator:  Final[int] = 1 << 1
    Supporter:  Final[int] = 1 << 2
    Owner:      Final[int] = 1 << 3
    Developer:  Final[int] = 1 << 4
    Tournament: Final[int] = 1 << 5 # NOTE: Not used in comms w/ osu!
