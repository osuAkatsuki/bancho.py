# -*- coding: utf-8 -*-
from collections import Sequence

from typing import Tuple, Union, Optional
from objects.player import Player
from objects.channel import Channel
from constants.privileges import Privileges
from console import printlog

Slice = Union[int, slice]

class ChannelList(Sequence):
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

    def get(self, name: str) -> Channel:
        for c in self.channels:
            if c.name == name:
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

class PlayerList(Sequence):
    def __init__(self):
        self.players = []

    def __getitem__(self, index: Slice) -> Player:
        return self.players[index]

    def __len__(self) -> int:
        return len(self.players)

    def __contains__(self, p: Union[Player, str]) -> bool:
        # Allow us to either pass in the player
        # obj, or the player name as a string.
        if isinstance(p, str):
            return p in (player.name for player in self.players)
        else:
            return p in self.players

    @property
    def ids(self) -> Tuple[int]:
        return (p.id for p in self.players)

    def broadcast(self, data: bytes) -> None:
        for p in self.players: # no idea if it takes ref
            p.enqueue(data)

    def get(self, token: str) -> Player:
        for p in self.players: # might copy
            if p.token == token:
                return p

    def get_by_name(self, name: str) -> Player:
        for p in self.players: # might copy
            if p.name == name:
                return p

    def get_by_id(self, id: int) -> Player:
        for p in self.players: # might copy
            if p.id == id:
                return p

    def add(self, p: Player) -> None: # bool ret success?
        if p in self.players:
            printlog(f'{p}) already in players list!')
            return
        printlog(f'Adding {p}) to players list.')
        self.players.append(p)

    def remove(self, p: Player) -> None:
        printlog(f'Removing {p}) from players list.')
        self.players.remove(p)
