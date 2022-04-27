from __future__ import annotations

__all__ = ("Privileges", "ClientPrivileges", "ClanPrivileges")


class Privileges:
    """Server side user privileges."""

    ANYONE = 0

    # privileges intended for all normal players.
    UNRESTRICTED = 1 << 0  # is an unbanned player.
    VERIFIED = 1 << 1  # has logged in to the server in-game.

    # has bypass to low-ceiling anticheat measures (trusted).
    WHITELISTED = 1 << 2

    # donation tiers, receives some extra benefits.
    SUPPORTER = 1 << 4
    PREMIUM = 1 << 5

    # notable users, receives some extra benefits.
    ALUMNI = 1 << 7

    # staff permissions, able to manage server app.state.
    TOURNEY_MANAGER = 1 << 10  # able to manage match state without host.
    NOMINATOR = 1 << 11  # able to manage maps ranked status.
    MODERATOR = 1 << 12  # able to manage users (level 1).
    ADMINISTRATOR = 1 << 13  # able to manage users (level 2).
    DEVELOPER = 1 << 14  # able to manage full server app.state.

    DONATOR = SUPPORTER | PREMIUM
    STAFF = MODERATOR | ADMINISTRATOR | DEVELOPER


def privileges_to_str(privileges: int) -> str:
    privilege_strings = []

    if privileges & Privileges.UNRESTRICTED:
        privilege_strings.append("Unrestricted")
    if privileges & Privileges.VERIFIED:
        privilege_strings.append("Verified")
    if privileges & Privileges.WHITELISTED:
        privilege_strings.append("Whitelisted")
    if privileges & Privileges.SUPPORTER:
        privilege_strings.append("Supporter")
    if privileges & Privileges.PREMIUM:
        privilege_strings.append("Premium")
    if privileges & Privileges.ALUMNI:
        privilege_strings.append("Alumni")
    if privileges & Privileges.TOURNEY_MANAGER:
        privilege_strings.append("Tourney Manager")
    if privileges & Privileges.NOMINATOR:
        privilege_strings.append("Nominator")
    if privileges & Privileges.MODERATOR:
        privilege_strings.append("Moderator")
    if privileges & Privileges.ADMINISTRATOR:
        privilege_strings.append("Administrator")
    if privileges & Privileges.DEVELOPER:
        privilege_strings.append("Developer")

    return " | ".join(privilege_strings)


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
