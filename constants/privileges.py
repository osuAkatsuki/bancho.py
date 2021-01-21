# -*- coding: utf-8 -*-

from enum import IntFlag
from enum import unique

__all__ = ('Privileges', 'ClientPrivileges')

@unique
class Privileges(IntFlag):
    """Server side user privileges."""

    # privileges intended for all normal players.
    Normal      = 1 << 0 # is an unbanned player.
    Verified    = 1 << 1 # has logged in to the server in-game.

    # has bypass to low-ceiling anticheat measures (trusted).
    Whitelisted = 1 << 2

    # donation tiers, receives some extra benefits.
    Supporter   = 1 << 4
    Premium     = 1 << 5

    # notable users, receives some extra benefits.
    Alumni      = 1 << 7

    # staff permissions, able to manage server state.
    Tournament  = 1 << 10 # able to manage match state without host.
    Nominator   = 1 << 11 # able to manage maps ranked status.
    Mod         = 1 << 12 # able to manage users (level 1).
    Admin       = 1 << 13 # able to manage users (level 2).
    Dangerous   = 1 << 14 # able to manage full server state.

    Donator = Supporter | Premium
    Staff = Mod | Admin | Dangerous

@unique
class ClientPrivileges(IntFlag):
    """Client side user privileges."""

    Player     = 1 << 0
    Moderator  = 1 << 1
    Supporter  = 1 << 2
    Owner      = 1 << 3
    Developer  = 1 << 4
    Tournament = 1 << 5 # NOTE: not used in communications with osu! client
