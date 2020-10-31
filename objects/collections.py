# -*- coding: utf-8 -*-

from typing import Union, Optional
from cmyui import log

from objects.player import Player
from objects.channel import Channel
from objects.match import Match
from constants.privileges import Privileges
from objects import glob

__all__ = (
    'Slice',
    'ChannelList',
    'MatchList',
    'PlayerList'
)

# NOTE: these should all inherit from a base class,
# a lot of their functionality is common between all.

Slice = Union[int, slice]

class ChannelList:
    """A class to represent all chat channels on the gulag.

    Attributes
    -----------
    channels: list[`Channel`]
        A list of channel objects representing the current chat channels.
    """
    __slots__ = ('channels',)

    def __init__(self):
        self.channels: list[Channel] = []

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
        # allow us to either pass in the channel
        # obj, or the channel name as a string.
        if isinstance(c, str):
            return c in [chan.name for chan in self.channels]
        else:
            return c in self.channels

    def get(self, name: str) -> Optional[Channel]:
        """Get a channel from the list by `name`."""
        for c in self.channels:
            if c._name == name:
                return c

    async def add(self, c: Channel) -> None:
        """Attempt to add `c` to the list."""
        if c in self.channels:
            log(f'{c} double-added to channels list?')
            return

        self.channels.append(c)

        if glob.config.debug:
            log(f'{c} added to channels list.')

    async def remove(self, c: Channel) -> None:
        """Attempt to remove `c` from the list."""
        self.channels.remove(c)

        if glob.config.debug:
            log(f'{c} removed from channels list.')

class MatchList:
    """A class to represent all multiplayer matches on the gulag.

    Attributes
    -----------
    matches: list[Optional[`Match`]]
        A list of match objects representing the current mp matches.
        The size of this attr is constant; slots will be None if not in use.
    """
    __slots__ = ('matches',)

    def __init__(self):
        self.matches = [None for _ in range(32)] # max matches.

    def __getitem__(self, index: Slice) -> Optional[Match]:
        return self.matches[index]

    def __len__(self) -> int:
        return len(self.matches)

    def __contains__(self, m: Match) -> bool:
        return m in self.matches

    def get_free(self) -> Optional[int]:
        # return first free match slot.
        for idx, m in enumerate(self.matches):
            if not m:
                return idx

    async def add(self, m: Match) -> None:
        """Attempt to add `m` to the list."""
        if m in self.matches:
            log(f'{m} double-added to matches list?')
            return

        if (free := self.get_free()) is not None:
            # set the id of the match
            # to our free slot found.
            m.id = free
            self.matches[free] = m

            if glob.config.debug:
                log(f'{m} added to matches list.')
        else:
            log(f'Match list is full! Could not add {m}.')

    async def remove(self, m: Match) -> None:
        """Attempt to remove `m` from the list."""
        for idx, i in enumerate(self.matches):
            if m == i:
                self.matches[idx] = None
                break

        if glob.config.debug:
            log(f'{m} removed from matches list.')

class PlayerList:
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
        # allow us to either pass in the player
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
        name_safe = Player.make_safe(name)

        for p in self.players:
            if p.safe_name == name_safe:
                return p

        if not sql:
            # don't fetch from sql
            # if not specified.
            return

        # try to get from sql.
        res = await glob.db.fetch(
            'SELECT id, priv, silence_end '
            'FROM users WHERE name_safe = %s',
            [name_safe]
        )

        return Player(**res, name=name) if res else None

    async def get_by_id(self, pid: int, sql: bool = False) -> Optional[Player]:
        for p in self.players:
            if p.id == pid:
                return p

        if not sql:
            # don't fetch from sql
            # if not specified.
            return

        # try to get from sql.
        res = await glob.db.fetch(
            'SELECT name, priv, silence_end '
            'FROM users WHERE id = %s',
            [pid]
        )

        return Player(**res, id=pid) if res else None

    async def get_login(self, name: str, phash: str) -> Optional[Player]:
        # only used cached results - the user should have
        # logged into bancho at least once. (This does not
        # mean they're logged in now).

        # let them pass as a string for ease of access
        phash = phash.encode()

        bcrypt_cache = glob.cache['bcrypt']

        if phash not in bcrypt_cache:
            # player has not logged in through bancho.
            return

        res = await glob.db.fetch(
            'SELECT pw_hash FROM users '
            'WHERE name_safe = %s',
            [Player.make_safe(name)]
        )

        if not res:
            # could not find the player in sql.
            return

        if bcrypt_cache[phash] != res['pw_hash']:
            # password bcrypts do not match.
            return

        return await self.get_by_name(name)

    def add(self, p: Player) -> None:
        """Attempt to add `p` to the list."""
        if p in self.players:
            if glob.config.debug:
                log(f'{p} double-added to global player list?')
            return

        self.players.append(p)

        if glob.config.debug:
            log(f'{p} added to global player list.')

    def remove(self, p: Player) -> None:
        """Attempt to remove `p` from the list."""
        self.players.remove(p)

        if glob.config.debug:
            log(f'{p} removed from global player list.')
