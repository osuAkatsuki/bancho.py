# -*- coding: utf-8 -*-

from typing import Tuple, Union
from objects.player import Player
from constants.privileges import Privileges

class Channel:
    def __init__(self, *args, **kwargs) -> None:
        self.name = kwargs.get('name', None)
        self.topic = kwargs.get('topic', None)
        self.players = []

        self.read = kwargs.get('read', Privileges.Verified)
        self.write = kwargs.get('write', Privileges.Verified)
        self.auto_join = kwargs.get('auto_join', True)

    def __contains__(self, p: Player) -> bool:
        return p in self.players

    def append(self, p: Player) -> None:
        self.players.append(p)
    def remove(self, p: Player) -> None:
        self.players.remove(p)

    def enqueue(self, data: bytes, immune = []) -> None:
        # Enqueue bytes to all players in a channel.
        # Usually just used for messages.. perhaps more?
        for p in self.players:
            if p.id in immune:
                continue
            p.enqueue(data)

    @property
    def basic_info(self) -> Tuple[Union[str, int]]:
        return (self.name, self.topic, len(self.players))

    ''' I can't think of any reason these shouldn't just be a part of the Player class? '''

    #def join(self, p: Player) -> bool:
    #    if not p.priv & self.read:
    #        print(f'{p.name} tried to join {self.name} which they have no access for.')
    #        return False

    #    if p in self.players:
    #        print(f'{p.name} tried to join {self.name} which they are already in.')
    #        return False

    #    self.players.append(p)
    #    p.join_channel(self)
    #    return True

    #def leave(self, p: Player) -> None:
    #    if p not in self.players:
    #        print(f'{p.name} tried to leave {self.name} which they are not in.')
    #        return

    #    p.leave_channel(self)
    #    self.players.remove(p)
