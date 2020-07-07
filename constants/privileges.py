# -*- coding: utf-8 -*-

from typing import Final
from enum import IntFlag, unique

@unique
class Privileges(IntFlag):
    # Design inspired from rumoi/ruri.
    # https://github.com/rumoi/ruri/blob/master/ruri/Source.cpp#L13-L42
    # Spaces left for possible future changes.
    Banned: Final[int] = 0
    Verified: Final[int] = 1 << 0 # Has verified their account.
    Visible: Final[int] = 1 << 1 # Can be seen by normal users.
    Whitelisted: Final[int] = 1 << 2 # Can bypass basic anticheat measures.
    Tournament: Final[int] = 1 << 3 # Is a referee in every match they join.

    Supporter: Final[int] = 1 << 5 # Has tier 1 donor.
    Premium: Final[int] = 1 << 6 # Has tier 2 donor.

    Nominator: Final[int] = 1 << 9 # Can change the ranked-status of beatmaps.
    Mod: Final[int] = 1 << 10 # Can use basic moderation tools (silence, kick).

    Admin: Final[int] = 1 << 14 # Can access user information, and restrict/ban/etc.
    Dangerous: Final[int] = 1 << 18 # Can access potentially dangerous information.

@unique
class BanchoPrivileges(IntFlag):
    Player: Final[int] = 1 << 0
    Moderator: Final[int] = 1 << 1
    Supporter: Final[int] = 1 << 2
    Owner: Final[int] = 1 << 3
    Developer: Final[int] = 1 << 4
    Tournament: Final[int] = 1 << 5 # Note: not sent to/from client/server
