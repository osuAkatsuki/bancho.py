# -*- coding: utf-8 -*-

from typing import Tuple, Set, Union
from constants.privileges import Privileges
from objects import glob
import packets

class Channel:
    def __init__(self, *args, **kwargs) -> None:
        # Use this attribute whenever you need
        # the 'real' name and not the wrapped one.
        # (not replaced for #multiplayer/#spectator)

        # self.name should be used whenever
        # interacting with the osu! client.
        self._name = kwargs.get('name', None)
        self.topic = kwargs.get('topic', None)
        self.players = []

        self.read = kwargs.get('read', Privileges.Verified)
        self.write = kwargs.get('write', Privileges.Verified)
        self.auto_join = kwargs.get('auto_join', True)
        self.temp = kwargs.get('temp', False)

    @property
    def name(self) -> str:
        if self._name.startswith('#spec_'):
            return '#spectator'
        elif self._name.startswith('#multi_'):
            return '#multiplayer'

        return self._name

    @property
    def basic_info(self) -> Tuple[Union[str, int]]:
        return (self.name, self.topic, len(self.players))

    def __repr__(self) -> str:
        return f'<{self._name}>'

    def __contains__(self, p) -> bool:
        return p in self.players

    def send(self, client, msg: str) -> None:
        self.enqueue(
            packets.sendMessage(
                client = client.name,
                msg = msg,
                target = self.name,
                client_id = client.id
            ), immune = {client.id}
        )

    def send_selective(self, client, msg: str, targets) -> None:
        # Accept a set of players to enqueue the data to.
        for p in targets:
            p.enqueue(
                packets.sendMessage(
                    client = client.name,
                    msg = msg,
                    target = self.name,
                    client_id = client.id
                ))

    def append(self, p) -> None:
        self.players.append(p)

    def remove(self, p) -> None:
        if len(self.players) == 1 and self.temp:
            # If it's a temporary channel and this
            # is the last member leaving, just remove
            # the channel from the global list.
            glob.channels.remove(self)
        else:
            self.players.remove(p)

    def enqueue(self, data: bytes, immune: Set[int] = {}) -> None:
        # Enqueue bytes to all players in a channel.
        # Usually just used for messages.. perhaps more?
        for p in self.players:
            if p.id in immune:
                continue
            p.enqueue(data)
