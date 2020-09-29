# -*- coding: utf-8 -*-

from enum import IntFlag, unique

__all__ = ('Privileges', 'BanchoPrivileges')

@unique
class Privileges(IntFlag):
    """A class to represent user privileges server-side.
    Gaps inbetween groups are left for future changes.
    """

    # A normal vanilla user, access intended for all users.
    # XXX: If a user does not have this bit, they are banned.
    Normal      = 1 << 0

    # Has bypass to low-ceiling anticheat measures (trusted).
    Whitelisted = 1 << 1

    # Donation tiers, receives some extra benefits.
    Supporter   = 1 << 4
    Premium     = 1 << 5

    # Notable users, receives some extra benefits.
    Alumni      = 1 << 7

    # Staff permissions, able to manage server state.
    Tournament  = 1 << 10 # Able to manage match state without host.
    Nominator   = 1 << 11 # Able to manage maps ranked status.
    Mod         = 1 << 12 # Able to manage users (level 1).
    Admin       = 1 << 13 # Able to manage users (level 2).
    Dangerous   = 1 << 14 # Able to manage full server state.

    Staff = Mod | Admin | Dangerous

@unique
class BanchoPrivileges(IntFlag):
    Player     = 1 << 0
    Moderator  = 1 << 1
    Supporter  = 1 << 2
    Owner      = 1 << 3
    Developer  = 1 << 4
    Tournament = 1 << 5 # NOTE: Not used in comms w/ osu!
