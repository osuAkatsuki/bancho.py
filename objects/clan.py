# -*- coding: utf-8 -*-

from datetime import datetime
from enum import IntEnum, unique

__all__ = 'Clan', 'ClanRank'

@unique
class ClanRank(IntEnum):
    """A class to represent a clan members rank."""
    Member = 1
    Officer = 2
    Owner = 3

class Clan:
    """A class to represent a single gulag clan."""
    __slots__ = ('id', 'name', 'tag', 'created_at',
                 'owner', 'members')

    def __init__(self, id: int, name: str, tag: str,
                 owner: int, created_at: datetime,
                 members: set[int] = set()) -> None:
        """A class representing one of gulag's clans."""
        self.id = id
        self.name = name
        self.tag = tag
        self.created_at = created_at

        self.owner = owner # userid
        self.members = members # userids

    def __repr__(self) -> str:
        return f'[{self.tag}] {self.name}'
