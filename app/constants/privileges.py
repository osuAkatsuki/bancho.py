from __future__ import annotations

__all__ = ("Privileges", "ClientPrivileges", "ClanPrivileges")


class Privileges:
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

    # staff permissions, able to manage server app.state.
    TOURNAMENT = 1 << 10  # able to manage match state without host.
    NOMINATOR = 1 << 11  # able to manage maps ranked status.
    MODERATOR = 1 << 12  # able to manage users (level 1).
    ADMINISTRATOR = 1 << 13  # able to manage users (level 2).
    DEVELOPER = 1 << 14  # able to manage full server app.state.

    DONATOR = SUPPORTER | PREMIUM
    STAFF = MODERATOR | ADMINISTRATOR | DEVELOPER


def privileges_to_str(privileges: int) -> str:
    l = []

    if privileges & Privileges.NORMAL:
        l.append("Normal")
    if privileges & Privileges.VERIFIED:
        l.append("Verified")
    if privileges & Privileges.WHITELISTED:
        l.append("Whitelisted")
    if privileges & Privileges.SUPPORTER:
        l.append("Supporter")
    if privileges & Privileges.PREMIUM:
        l.append("Premium")
    if privileges & Privileges.ALUMNI:
        l.append("Alumni")
    if privileges & Privileges.TOURNAMENT:
        l.append("Tournament")
    if privileges & Privileges.NOMINATOR:
        l.append("Nominator")
    if privileges & Privileges.MODERATOR:
        l.append("Moderator")
    if privileges & Privileges.ADMINISTRATOR:
        l.append("Administrator")
    if privileges & Privileges.DEVELOPER:
        l.append("Developer")

    return " | ".join(l)


class ClientPrivileges:
    """Client side user privileges."""

    PLAYER = 1 << 0
    MODERATOR = 1 << 1
    SUPPORTER = 1 << 2
    OWNER = 1 << 3
    DEVELOPER = 1 << 4
    TOURNAMENT = 1 << 5  # NOTE: not used in communications with osu! client


class ClanPrivileges:
    """A class to represent a clan members privs."""

    MEMBER = 1
    OFFICER = 2
    OWNER = 3
