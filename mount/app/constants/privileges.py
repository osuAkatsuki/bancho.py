from enum import IntFlag
from enum import unique

from mount.app.utils import escape_enum
from mount.app.utils import pymysql_encode

__all__ = ("Privileges", "ClientPrivileges")


@unique
@pymysql_encode(escape_enum)
class Privileges(IntFlag):
    """Server side user privileges."""

    # privileges intended for all normal players.
    NORMAL = 1 << 0  # is an unbanned player.
    VERIFIED = 1 << 1  # has logged in to the server in-game.

    # has bypass to low-ceiling anticheat measures (trusted).
    WHITELISTED = 1 << 2

    # donation tiers, receives some extra benefits.
    SUPPORTER = 1 << 4
    PREMIUM = 1 << 5

    # notable users, receives some extra benefits.
    ALUMNI = 1 << 7

    # staff permissions, able to manage server state.
    TOURNAMENT = 1 << 10  # able to manage match state without host.
    NOMINATOR = 1 << 11  # able to manage maps ranked status.
    MODERATOR = 1 << 12  # able to manage users (level 1).
    ADMINISTRATOR = 1 << 13  # able to manage users (level 2).
    DEVELOPER = 1 << 14  # able to manage full server state.

    DONATOR = SUPPORTER | PREMIUM
    STAFF = MODERATOR | ADMINISTRATOR | DEVELOPER


@unique
@pymysql_encode(escape_enum)
class ClientPrivileges(IntFlag):
    """Client side user privileges."""

    PLAYER = 1 << 0
    MODERATOR = 1 << 1
    SUPPORTER = 1 << 2
    OWNER = 1 << 3
    DEVELOPER = 1 << 4
    TOURNAMENT = 1 << 5  # NOTE: not used in communications with osu! client
