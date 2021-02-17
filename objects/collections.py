# -*- coding: utf-8 -*-

# TODO: there is still a lot of inconsistency
# in a lot of these classes; needs refactor.

from typing import Any, Optional
from typing import TYPE_CHECKING
from typing import Union

from cmyui import log

from constants.privileges import Privileges
from objects import glob
from objects.clan import ClanPrivileges
from objects.player import Player
from utils.misc import make_safe_name

if TYPE_CHECKING:
    from objects.channel import Channel
    from objects.match import Match, MapPool
    from objects.clan import Clan

__all__ = (
    'ChannelList',
    'MatchList',
    'PlayerList',
    'MapPoolList',
    'ClanList'
)

class ChannelList(list):
    """The currently active chat channels on the server."""

    def __contains__(self, o: Union['Channel', str]) -> bool:
        """Check whether internal list contains `o`."""
        # Allow string to be passed to compare vs. name.
        if isinstance(o, str):
            return o in map(lambda c: c.name, self)
        else:
            return super().__contains__(o)

    def __getitem__(self, index: Union[int, slice, str]) -> 'Channel':
        # XXX: can be either a string (to get by name),
        # or a slice, for indexing the internal array.
        if isinstance(index, str):
            return self.get(index)
        else:
            return self[index]

    def __repr__(self) -> str:
        # XXX: we use the "real" name, aka
        # #multi_1 instead of #multiplayer
        # #spect_1 instead of #spectator.
        return f'[{", ".join(c._name for c in self)}]'

    def get(self, name: str) -> Optional['Channel']:
        """Get a channel from the list by `name`."""
        for c in self:
            if c._name == name:
                return c

    def append(self, c: 'Channel') -> None:
        """Append `c` to internal list."""
        super().append(c)

        if glob.config.debug:
            log(f'{c} added to channels list.')

    def remove(self, c: 'Channel') -> None:
        """Remove `c` from internal list."""
        super().remove(c)

        if glob.config.debug:
            log(f'{c} removed from channels list.')

class MatchList(list):
    """The currently active multiplayer matches on the server."""

    def __init__(self) -> None:
        super().__init__()
        self.extend([None] * 32)

    def __repr__(self) -> str:
        return f'[{", ".join(m.name for m in self if m)}]'

    def get_free(self) -> Optional[int]:
        """Return the first free slot id from `self`."""
        for idx, m in enumerate(self):
            if m is None:
                return idx

    def append(self, m: 'Match') -> bool:
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

    def remove(self, m: 'Match') -> None:
        for i, _m in enumerate(self):
            if m is _m:
                self[i] = None
                break

        if glob.config.debug:
            log(f'{m} removed from matches list.')

class PlayerList(list):
    """The currently active players on the server."""
    __slots__ = ('players',)

    def __contains__(self, p: Union[Player, str]) -> bool:
        # allow us to either pass in the player
        # obj, or the player name as a string.
        if isinstance(p, str):
            return p in [player.name for player in self]
        else:
            return super().__contains__(p)

    def __repr__(self) -> str:
        return f'[{", ".join(map(repr, self))}]'

    @property
    def ids(self) -> tuple[int, ...]:
        return (p.id for p in self)

    @property
    def staff(self) -> set[Player]:
        return {p for p in self if p.priv & Privileges.Staff}

    def enqueue(self, data: bytes, immune: tuple[Player, ...] = ()) -> None:
        for p in self:
            if p not in immune:
                p.enqueue(data)

    @staticmethod
    def _parse_attr(kwargs: dict[str, Any]) -> Optional[tuple[str, Any]]:
        """Get first matched attr & val from input kwargs. Used in get() methods."""
        for attr in ('token', 'id', 'name'):
            if val := kwargs.pop(attr, None):
                if attr == 'name':
                    attr = 'safe_name'
                    val = make_safe_name(val)

                return attr, val
        else:
            raise ValueError('Missing attribute in kwargs! (must provide token/id/name)')

    def get(self, **kwargs) -> Optional[Player]:
        """Get a player by token, id, or name from cache."""
        attr, val = self._parse_attr(kwargs)

        for p in self:
            if getattr(p, attr) == val:
                return p

    async def get_sql(self, **kwargs) -> Optional[Player]:
        """Get a player by token, id, or name from sql."""
        attr, val = self._parse_attr(kwargs)

        # try to get from sql.
        res = await glob.db.fetch(
            'SELECT id, name, priv, pw_bcrypt, '
            'silence_end, clan_id, clan_rank '
            f'FROM users WHERE {attr} = %s',
            [val]
        )

        if not res:
            return

        # overwrite some things with classes
        res['priv'] = Privileges(res['priv'])
        res['pw_bcrypt'] = bytes(res['pw_bcrypt'], encoding='utf-8')

        if res['clan_id'] != 0:
            res['clan'] = glob.clans.get(id=res['clan_id'])
            res['clan_rank'] = ClanPrivileges(res['clan_rank'])
        else:
            res['clan'] = res['clan_rank'] = None

        return Player(**res)

    async def get_ensure(self, **kwargs) -> Optional[Player]:
        """Try to get player from cache, or sql as fallback."""
        if p := self.get(**kwargs):
            return p
        elif p := await self.get_sql(**kwargs):
            return p

    async def get_login(self, name: str, pw_md5: str, sql: bool = False) -> Optional[Player]:
        # only used cached results - the user should have
        # logged into bancho at least once. (This does not
        # mean they're logged in now).

        if not (p := self.get(name=name)):
            if not sql: # not to fetch from sql.
                return

            if not (p := await self.get_sql(name=name)):
                # no player found in sql either.
                return

        if glob.cache['bcrypt'][p.pw_bcrypt] == pw_md5.encode():
            return p

    def append(self, p: Player) -> None:
        """Attempt to add `p` to the list."""
        if p in self:
            if glob.config.debug:
                log(f'{p} double-added to global player list?')
            return

        super().append(p)

        if glob.config.debug:
            log(f'{p} added to global player list.')

    def remove(self, p: Player) -> None:
        """Attempt to remove `p` from the list."""
        super().remove(p)

        if glob.config.debug:
            log(f'{p} removed from global player list.')

class MapPoolList(list):
    """The currently active mappools on the server."""

    def __getitem__(self, index: Union[int, slice, str]) -> 'MapPool':
        """Allow slicing by either a string (for name), or slice."""
        if isinstance(index, str):
            return self.get(index)
        else:
            return super().__getitem__(index)

    def __contains__(self, o: Union['MapPool', str]) -> bool:
        """Check whether internal list contains `o`."""
        # Allow string to be passed to compare vs. name.
        if isinstance(o, str):
            return o in [p.name for p in self]
        else:
            return o in self

    def get(self, name: str) -> Optional['MapPool']:
        """Get a pool from the list by `name`."""
        for p in self:
            if p.name == name:
                return p

    def append(self, p: 'MapPool') -> None:
        """Attempt to add `p` to the list."""
        super().append(p)

        if glob.config.debug:
            log(f'{p} added to mappools list.')

    def remove(self, p: 'MapPool') -> None:
        """Attempt to remove `p` from the list."""
        super().remove(p)

        if glob.config.debug:
            log(f'{p} removed from mappools list.')

class ClanList(list):
    """The currently active clans on the server."""

    def __getitem__(self, index: Union[int, slice, str]) -> 'Clan':
        """Allow slicing by either a string (for name), or slice."""
        if isinstance(index, str):
            return self.get(name=index)
        else:
            return super().__getitem__(index)

    def __contains__(self, o: Union['Clan', str]) -> bool:
        """Check whether internal list contains `o`."""
        # Allow string to be passed to compare vs. name.
        if isinstance(o, str):
            return o in [c.name for c in self]
        else:
            return o in self

    def get(self, **kwargs) -> Optional['Clan']:
        """Get a clan by name, tag, or id."""
        for attr in ('name', 'tag', 'id'):
            if val := kwargs.pop(attr, None):
                break
        else:
            raise ValueError('must provide valid kwarg (name, tag, id) to get()')

        for c in self:
            if getattr(c, attr) == val:
                return c

    def append(self, c: 'Clan') -> None:
        """Attempt to add `c` to the list."""
        super().append(c)

        if glob.config.debug:
            log(f'{c} added to clans list.')

    def remove(self, c: 'Clan') -> None:
        """Attempt to remove `c` from the list."""
        super().remove(c)

        if glob.config.debug:
            log(f'{c} removed from clans list.')
