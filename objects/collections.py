# -*- coding: utf-8 -*-

from typing import Tuple
from objects.player import Player
from objects.channel import Channel
from constants.privileges import Privileges
from console import printlog

class ChannelList:
    def __init__(self):
        self.channels = []

    def get(self, name: str) -> Channel:
        for c in self.channels:
            if c.name == name:
                return c

    def add(self, p: Channel) -> None: # bool ret success?
        if p in self.channels:
            printlog(f'{p.name} already in channels list!')
            return
        printlog(f'Adding {p.name} to channels list.')
        self.channels.append(p)

    def remove(self, p: Channel) -> None:
        printlog(f'Removing {p.name} from channels list.')
        self.channels.remove(p)

class PlayerList:
    def __init__(self):
        self.players = []

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
            printlog(f'{p.name} ({p.id}) already in players list!')
            return
        printlog(f'Adding {p.name} ({p.id}) to players list.')
        self.players.append(p)

    def remove(self, p: Player) -> None:
        printlog(f'Removing {p.name} ({p.id}) from players list.')
        self.players.remove(p)
