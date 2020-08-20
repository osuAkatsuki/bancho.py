# -*- coding: utf-8 -*-
from collections import Sequence

from typing import Tuple, Union, Optional
from objects.player import Player
from objects.channel import Channel
from objects.match import Match
from objects import glob
from console import printlog

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
    channels: List[:class:`Channel`]
        A list of channel objects representing the current chat channels.
    """
    __slots__ = ('channels',)

    def __init__(self):
        self.channels = []

    def __getitem__(self, index: Slice) -> Channel:
        return self.channels[index]

    def __len__(self) -> int:
        return len(self.channels)

    def __contains__(self, c: Union[Channel, str]) -> bool:
        # Allow us to either pass in the channel
        # obj, or the channel name as a string.
        if isinstance(c, str):
            return c in (chan.name for chan in self.channels)
        else:
            return c in self.channels

    def get(self, name: str) -> Optional[Channel]:
        for c in self.channels:
            if c._name == name:
                return c

    def add(self, c: Channel) -> None: # bool ret success?
        if c in self.channels:
            printlog(f'{c} already in channels list!')
            return
        printlog(f'Adding {c} to channels list.')
        self.channels.append(c)

    def remove(self, c: Channel) -> None:
        printlog(f'Removing {c} from channels list.')
        self.channels.remove(c)

class MatchList(Sequence):
    """A class to represent all multiplayer matches on the gulag.

    Attributes
    -----------
    matches: List[Optional[:class:`Match`]]
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
            if not m: return idx

    def get_by_id(self, mid: int) -> Optional[Match]:
        for m in self.matches:
            if m and m.id == mid:
                return m

    def add(self, m: Match) -> bool:
        if m in self.matches:
            printlog(f'{m} already in matches list!')
            return False

        if (free := self.get_free()) is None:
            printlog(f'Match list is full! Could not add {m}.')
            return False

        m.id = free
        printlog(f'Adding {m} to matches list.')
        self.matches[free] = m

    def remove(self, m: Match) -> None:
        printlog(f'Removing {m} from matches list.')
        for idx, _m in enumerate(self.matches):
            if m == _m:
                self.matches[idx] = None
                break

class PlayerList(Sequence):
    """A class to represent all players online on the gulag.

    Attributes
    -----------
    players: List[:class:`Player`]
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
            return p in (player.name for player in self.players)
        else:
            return p in self.players

    def __len__(self) -> int:
        return len(self.players)

    @property
    def ids(self) -> Tuple[int, ...]:
        return (p.id for p in self.players)

    def enqueue(self, data: bytes, immune: Tuple[Player, ...] = ()) -> None:
        for p in self.players:
            if p not in immune:
                p.enqueue(data)

    def get(self, token: str) -> Player:
        for p in self.players: # might copy
            if p.token == token:
                return p

    def get_by_name(self, name: str, sql: bool = False) -> Player:
        for p in self.players: # might copy
            if p.name == name:
                return p

        if not sql:
            # Don't fetch from SQL
            # if not specified.
            return

        # Try to get from SQL.
        if not (res := glob.db.fetch(
            'SELECT id, priv, silence_end '
            'FROM users WHERE name = %s',
            [name]
        )): return

        return Player(**res)

    def get_by_id(self, pid: int) -> Player:
        for p in self.players: # might copy
            if p.id == pid:
                return p

    def get_from_cred(self, name: str, pw_md5: str) -> None:
        # Only used cached results - the user should have
        # logged into bancho at least once. (This does not
        # mean they're logged in now).

        # Let them pass as a string for ease of access
        pw_md5: bytes = pw_md5.encode()

        if pw_md5 not in glob.cache['bcrypt']:
            # User has not logged in through bancho.
            return

        res = glob.db.fetch(
            'SELECT pw_hash FROM users WHERE name_safe = %s',
            [Player.ensure_safe(name)])

        if not res:
            # Could not find user in the DB.
            return

        if glob.cache['bcrypt'][pw_md5] != res['pw_hash']:
            # Password bcrypts do not match.
            return

        return self.get_by_name(name)

    def add(self, p: Player) -> None: # bool ret success?
        if p in self.players:
            printlog(f'{p} already in players list!')
            return
        printlog(f'Adding {p} to players list.')
        self.players.append(p)

    def remove(self, p: Player) -> None:
        printlog(f'Removing {p} from players list.')
        self.players.remove(p)
