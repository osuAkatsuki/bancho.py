# -*- coding: utf-8 -*-

from typing import Union, Optional
from collections import Sequence

from objects.player import Player
from objects.channel import Channel
from objects.match import Match
from constants.privileges import Privileges
from objects import glob
from console import plog

__all__ = (
    'Slice',
    'ChannelList',
    'MatchList',
    'PlayerList'
)

Slice = Union[int, slice]

class ChannelList(Sequence):
    """A class to represent all chat channels on the gulag.

    Attributes
    -----------
    channels: list[`Channel`]
        A list of channel objects representing the current chat channels.
    """
    __slots__ = ('channels',)

    def __init__(self):
        self.channels = []

    def __getitem__(self, index: Union[Slice, str]) -> Channel:
        # XXX: can be either a string (to get by name),
        # or a slice, for indexing the internal array.
        if isinstance(index, str):
            return self.get(index)
        else:
            return self.channels[index]

    def __len__(self) -> int:
        return len(self.channels)

    def __contains__(self, c: Union[Channel, str]) -> bool:
        # Allow us to either pass in the channel
        # obj, or the channel name as a string.
        if isinstance(c, str):
            return c in [chan.name for chan in self.channels]
        else:
            return c in self.channels

    def get(self, name: str) -> Optional[Channel]:
        for c in self.channels:
            if c._name == name:
                return c

    async def add(self, c: Channel) -> None:
        if c in self.channels:
            await plog(f'{c} already in channels list!')
        else:
            await plog(f'Adding {c} to channels list.')
            self.channels.append(c)

    async def remove(self, c: Channel) -> None:
        await plog(f'Removing {c} from channels list.')
        self.channels.remove(c)

class MatchList(Sequence):
    """A class to represent all multiplayer matches on the gulag.

    Attributes
    -----------
    matches: list[Optional[`Match`]]
        A list of match objects representing the current mp matches.
        The size of this attr is constant; slots will be None if not in use.
    """
    __slots__ = ('matches',)

    def __init__(self):
        self.matches = [None for _ in range(32)] # Max matches.

    def __getitem__(self, index: Slice) -> Optional[Match]:
        return self.matches[index]

    def __len__(self) -> int:
        return len(self.matches)

    def __contains__(self, m: Match) -> bool:
        return m in self.matches

    def get_free(self) -> Optional[Match]:
        # Return first free match.
        for idx, m in enumerate(self.matches):
            if not m:
                return idx

    def get_by_id(self, mid: int) -> Optional[Match]:
        for m in self.matches:
            if m and m.id == mid:
                return m

    async def add(self, m: Match) -> None:
        if m in self.matches:
            await plog(f'{m} already in matches list!')
            return

        if (free := self.get_free()) is not None:
            m.id = free
            await plog(f'Adding {m} to matches list.')
            self.matches[free] = m
        else:
            await plog(f'Match list is full! Could not add {m}.')

    async def remove(self, m: Match) -> None:
        await plog(f'Removing {m} from matches list.')
        for idx, i in enumerate(self.matches):
            if m == i:
                self.matches[idx] = None
                break

class PlayerList(Sequence):
    """A class to represent all players online on the gulag.

    Attributes
    -----------
    players: list[`Player`]
        A list of player objects representing the online users.
    """
    __slots__ = ('players',)

    def __init__(self):
        self.players = []

    def __getitem__(self, index: Slice) -> Player:
        return self.players[index]

    def __contains__(self, p: Union[Player, str]) -> bool:
        # Allow us to either pass in the player
        # obj, or the player name as a string.
        if isinstance(p, str):
            return p in [player.name for player in self.players]
        else:
            return p in self.players

    def __len__(self) -> int:
        return len(self.players)

    @property
    def ids(self) -> tuple[int, ...]:
        return (p.id for p in self.players)

    @property
    def staff(self) -> set[Player]:
        return {p for p in self.players if p.priv & Privileges.Staff}

    def enqueue(self, data: bytes, immune: tuple[Player, ...] = ()) -> None:
        for p in self.players:
            if p not in immune:
                p.enqueue(data)

    def get(self, token: str) -> Player:
        for p in self.players:
            if p.token == token:
                return p

    async def get_by_name(self, name: str, sql: bool = False) -> Player:
        for p in self.players:
            if p.name == name:
                return p

        if not sql:
            # Don't fetch from SQL
            # if not specified.
            return

        # Try to get from SQL.
        res = await glob.db.fetch(
            'SELECT id, priv, silence_end '
            'FROM users WHERE name_safe = %s',
            [name]
        )

        return Player(**res, name=name) if res else None

    async def get_by_id(self, pid: int, sql: bool = False) -> Player:
        for p in self.players:
            if p.id == pid:
                return p

        if not sql:
            # Don't fetch from SQL
            # if not specified.
            return

        # Try to get from SQL.
        res = await glob.db.fetch(
            'SELECT name, priv, silence_end '
            'FROM users WHERE id = %s',
            [pid]
        )

        return Player(**res, id = pid) if res else None

    async def get_login(self, name: str, phash: str) -> Optional[Player]:
        # Only used cached results - the user should have
        # logged into bancho at least once. (This does not
        # mean they're logged in now).

        # Let them pass as a string for ease of access
        phash = phash.encode()

        bcrypt_cache = glob.cache['bcrypt']

        if phash not in bcrypt_cache:
            # User has not logged in through bancho.
            return

        res = await glob.db.fetch(
            'SELECT pw_hash FROM users '
            'WHERE name_safe = %s',
            [Player.make_safe(name)]
        )

        if not res:
            # Could not find user in the DB.
            return

        if bcrypt_cache[phash] != res['pw_hash']:
            # Password bcrypts do not match.
            return

        return await self.get_by_name(name)

    async def add(self, p: Player) -> None:
        if p in self.players:
            await plog(f'{p} already in players list!')
            return

        await plog(f'Adding {p} to players list.')
        self.players.append(p)

    async def remove(self, p: Player) -> None:
        await plog(f'Removing {p} from players list.')
        self.players.remove(p)
