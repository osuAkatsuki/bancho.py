# -*- coding: utf-8 -*-

from typing import Tuple
from constants.privileges import Privileges
from objects import glob
import packets

__all__ = ('Channel',)

class Channel:
    """A class to represent a chat channel.

    Attributes
    -----------
    _name: :class:`str`
        A name string of the channel.
        The cls.`name` property wraps handling for '#multiplayer' and
        '#spectator' when communicating with the osu! client; only use
        this attr when you need the channel's true name; otherwise you
        should use the `name` property described below.

    topic: :class:`str`
        The topic string of the channel.

    players: List[:class:`Player`]
        A list of player objects representing the players in the channel.
        XXX: While channels store a list of player objs, players also
             store a list of channel objs for channels they're in.

    read: :class:`Privileges`
        The privileges required to read messages in the channel.

    write: :class:`Privileges`
        The privileges required to write messages in the channel.

    auto_join: :class:`bool`
        A bool representing whether the channel should automatically
        be joined on connection to the server.

    temp: :class:`bool`
        A bool representing whether the channel is 'temporary'.
        Temporary channels are deleted when all players have left;
        this is useful for things like multiplayer, spectator, etc.

    Properties
    -----------
    name: :class:`str`
        A name string of the channel with #spec_x and #multi_x
        replaced with the more readable '#spectator' and '#multiplayer'.

    basic_info: Tuple[Union[:class:`str`, :class:`str`, :class:`int`]]
        A tuple containing the channel's name
        (clean output), topic, and playercount.
    """
    __slots__ = ('_name', 'topic', 'players',
                 'read', 'write', 'auto_join', 'temp')

    def __init__(self, *args, **kwargs) -> None:
        # Use this attribute whenever you need
        # the 'real' name and not the wrapped one.
        # (not replaced for #multiplayer/#spectator)

        # self.name should be used whenever
        # interacting with the osu! client.
        self._name = kwargs.get('name', None)
        self.topic = kwargs.get('topic', None)
        self.players = []

        self.read = kwargs.get('read', Privileges.Normal)
        self.write = kwargs.get('write', Privileges.Normal)
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
    def basic_info(self) -> Tuple[str, str, int]:
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

    def enqueue(self, data: bytes, immune: Tuple[int, ...] = ()) -> None:
        # Enqueue bytes to all players in a channel.
        # Usually just used for messages.. perhaps more?
        for p in self.players:
            if p.id in immune:
                continue
            p.enqueue(data)
