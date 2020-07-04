# -*- coding: utf-8 -*-

from typing import Tuple, Set, Union
from objects.player import Player
from constants.privileges import Privileges
from objects import glob
import packets

class Channel:
    def __init__(self, *args, **kwargs) -> None:
        self.name = kwargs.get('name', None)
        self.topic = kwargs.get('topic', None)
        self.players = []

        self.read = kwargs.get('read', Privileges.Verified)
        self.write = kwargs.get('write', Privileges.Verified)
        self.auto_join = kwargs.get('auto_join', True)
        self.temp = kwargs.get('temp', False)

    @property
    def basic_info(self) -> Tuple[Union[str, int]]:
        return (self.name, self.topic, len(self.players))

    def __repr__(self) -> str:
        return f'<{self.name}>'

    def __contains__(self, p: Player) -> bool:
        return p in self.players

    def send(self, client: Player, msg: str) -> None:
        self.enqueue(
            packets.sendMessage(
                client = client.name,
                msg = msg,
                target = self.name,
                client_id = client.id
            ), immune = {client.id}
        )

    def send_selective(self, client: Player, msg: str, targets: Set[Player]) -> None:
        # Accept a set of players to enqueue the data to.
        for p in targets:
            p.enqueue(
                packets.sendMessage(
                    client = client.name,
                    msg = msg,
                    target = self.name,
                    client_id = client.id
                ))

    def append(self, p: Player) -> None:
        self.players.append(p)

    def remove(self, p: Player) -> None:
        if len(self.players) == 1 and self.temp:
            # If it's a temporary channel and this
            # is the last member leaving, just remove
            # the channel from the global list.
            glob.channels.remove(self)
        else:
            self.players.remove(p)

    def enqueue(self, data: bytes, immune: Set[int] = []) -> None:
        # Enqueue bytes to all players in a channel.
        # Usually just used for messages.. perhaps more?
        for p in self.players:
            if p.id in immune:
                continue
            p.enqueue(data)
