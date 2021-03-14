# -*- coding: utf-8 -*-

from typing import TYPE_CHECKING

import packets
from constants.privileges import Privileges
from objects import glob

if TYPE_CHECKING:
    from objects.player import Player

__all__ = 'Channel',

class Channel:
    """An osu! chat channel.

    Possibly confusing attributes
    -----------
    _name: `str`
        A name string of the channel.
        The cls.`name` property wraps handling for '#multiplayer' and
        '#spectator' when communicating with the osu! client; only use
        this attr when you need the channel's true name; otherwise you
        should use the `name` property described below.

    instance: `bool`
        Instanced channels are deleted when all players have left;
        this is useful for things like multiplayer, spectator, etc.
    """
    __slots__ = ('_name', 'topic', 'players',
                 'read_priv', 'write_priv',
                 'auto_join', 'instance')

    def __init__(self, name: str, topic: str,
                 read_priv: Privileges = Privileges.Normal,
                 write_priv: Privileges = Privileges.Normal,
                 auto_join: bool = True,
                 instance: bool = False) -> None:
        self._name = name # 'real' name ('#{multi/spec}_{id}')
        self.topic = topic
        self.read_priv = read_priv
        self.write_priv = write_priv
        self.auto_join = auto_join
        self.instance = instance

        self.players: list['Player'] = []

    @property
    def name(self) -> str:
        if self._name.startswith('#spec_'):
            return '#spectator'
        elif self._name.startswith('#multi_'):
            return '#multiplayer'
        else:
            return self._name

    @property
    def basic_info(self) -> tuple[str, str, int]:
        return (self.name, self.topic, len(self.players))

    def __repr__(self) -> str:
        return f'<{self._name}>'

    def __contains__(self, p: 'Player') -> bool:
        return p in self.players

    def send(self, msg: str, sender: 'Player',
             to_self: bool = False) -> None:
        """Enqueue `msg` to all connected clients from `sender`."""
        self.enqueue(
            packets.sendMessage(
                sender = sender.name,
                msg = msg,
                recipient = self.name,
                sender_id = sender.id
            ),
            immune = () if to_self else (sender.id,)
        )

    def send_bot(self, msg: str) -> None:
        """Enqueue `msg` to all connected clients from bot."""
        bot = glob.bot

        self.enqueue(
            packets.sendMessage(
                sender = bot.name,
                msg = msg,
                recipient = self.name,
                sender_id = bot.id
            )
        )

    def send_selective(self, msg: str, sender: 'Player',
                       recipients: list['Player']) -> None:
        """Enqueue `sender`'s `msg` to `recipients`."""
        for p in [t for t in recipients if t in self]:
            p.send(msg, sender=sender, chan=self)

    def append(self, p: 'Player') -> None:
        """Add `p` to the channel's players."""
        self.players.append(p)

    def remove(self, p: 'Player') -> None:
        """Remove `p` from the channel's players."""
        self.players.remove(p)

        if len(self.players) == 0 and self.instance:
            # if it's an instance channel and this
            # is the last member leaving, just remove
            # the channel from the global list.
            glob.channels.remove(self)

    def enqueue(self, data: bytes, immune: tuple[int, ...] = ()) -> None:
        """Enqueue `data` to all connected clients not in `immune`."""
        for p in self.players:
            if p.id not in immune:
                p.enqueue(data)
