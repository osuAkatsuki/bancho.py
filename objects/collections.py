# -*- coding: utf-8 -*-

from typing import Union, Optional
from cmyui import log

from objects.player import Player
from objects.channel import Channel
from objects.match import Match, MapPool
from constants.privileges import Privileges
from objects import glob

__all__ = (
    'ChannelList',
    'MatchList',
    'PlayerList',
    'MapPoolList'
)

class ChannelList(list):
    """The currently active chat channels on the server."""

    def __contains__(self, o: Union[Channel, str]) -> bool:
        """Check whether internal list contains `o`."""
        # Allow string to be passed to compare vs. name.
        if isinstance(o, str):
            return o in map(lambda c: c.name, self)
        else:
            return super().__contains__(o)

    def __getitem__(self, index: Union[int, slice, str]) -> Channel:
        # XXX: can be either a string (to get by name),
        # or a slice, for indexing the internal array.
        if isinstance(index, str):
            return self.get(index)
        else:
            return self[index]

    def get(self, name: str) -> Optional[Channel]:
        """Get a channel from the list by `name`."""
        for c in self:
            if c._name == name:
                return c

    def append(self, c: Channel) -> None:
        """Append `c` to internal list."""
        if glob.config.debug:
            log(f'{c} added to channels list.')

        return super().append(c)

    def remove(self, c: Channel) -> None:
        """Remove `c` from internal list."""
        if glob.config.debug:
            log(f'{c} removed from channels list.')

        return super().remove(c)

class MatchList(list):
    """The currently active multiplayer matches on the server."""

    def __init__(self) -> None:
        super().__init__()
        self.extend([None] * 32)

    def get_free(self) -> Optional[int]:
        """Return the first free slot id from `self`."""
        for idx, m in enumerate(self):
            if m is None:
                return idx

    def append(self, m: Match) -> bool:
        if m in self:
            breakpoint()

        if (free := self.get_free()) is not None:
            # set the id of the match to the free slot.
            m.id = free
            self[free] = m

            if glob.config.debug:
                log(f'{m} added to matches list.')

            return True
        else:
            log(f'Match list is full! Could not add {m}.')
            return False

    def remove(self, m: Match) -> None:
        for i, _m in enumerate(self):
            if m is _m:
                self[i] = None
                break

        if glob.config.debug:
            log(f'{m} removed from matches list.')

class PlayerList:
    """The currently active players on the server."""
    __slots__ = ('players',)

    def __init__(self):
        self.players = []

    def __getitem__(self, index: Union[int, slice]) -> Player:
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

    async def get(self, sql: bool = False, **kwargs) -> Optional[Player]:
        for attr in ('token', 'id', 'name'):
            if val := kwargs.pop(attr, None):
                break
        else:
            raise ValueError('must provide valid kwarg (token, id, name) to get()')

        if attr == 'name':
            # name -> safe_name
            attr = 'safe_name'
            val = Player.make_safe(val)

        for p in self.players:
            if getattr(p, attr) == val:
                return p

        if not sql:
            # don't fetch from sql
            # if not specified
            return

        # try to get from sql.
        res = await glob.db.fetch(
            'SELECT id, name, priv, pw_bcrypt, silence_end '
            f'FROM users WHERE {attr} = %s',
            [val]
        )

        if not res:
            return

        priv = Privileges(res.pop('priv'))
        return Player(**res, priv=priv)

    async def get_login(self, name: str, pw_md5: str, sql: bool = False) -> Optional[Player]:
        # only used cached results - the user should have
        # logged into bancho at least once. (This does not
        # mean they're logged in now).

        # let them pass as a string for ease of access
        pw_md5 = pw_md5.encode()

        bcrypt_cache = glob.cache['bcrypt']

        if pw_md5 not in bcrypt_cache:
            # player has not logged in through bancho.
            return

        if not (p := await self.get(name=name, sql=sql)):
            return # no such player online

        # return if bcrypt matches
        if bcrypt_cache[pw_md5] == p.pw_bcrypt:
            return p

    def append(self, p: Player) -> None:
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

class MapPoolList(list):
    """The currently active mappools on the server."""

    def __getitem__(self, index: Union[int, slice, str]) -> MapPool:
        # XXX: can be either a string (to get by name),
        # or a slice, for indexing the internal array.
        if isinstance(index, str):
            return self.get(index)
        else:
            return super().__getitem__(index)

    def __contains__(self, o: Union[MapPool, str]) -> bool:
        """Check whether internal list contains `o`."""
        # Allow string to be passed to compare vs. name.
        if isinstance(o, str):
            return o in [p.name for p in self]
        else:
            return o in self

    def get(self, name: str) -> Optional[MapPool]:
        """Get a pool from the list by `name`."""
        for p in self:
            if p.name == name:
                return p

    def append(self, p: MapPool) -> None:
        """Attempt to add `p` to the list."""
        super().append(p)

        if glob.config.debug:
            log(f'{p} added to mappools list.')

    def remove(self, p: MapPool) -> None:
        """Attempt to remove `p` from the list."""
        super().remove(p)

        if glob.config.debug:
            log(f'{p} removed from mappools list.')
