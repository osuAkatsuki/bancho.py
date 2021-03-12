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
    name: `str`
        A name string of the channel.
        The cls.`name` attribute is what the client sees (i.e. #multiplayer). This does not
        contain identification information pertaining to the channel, only information for
        the client.

    id_name: `str`
        A special name string of the channel.
        The cls.`id_name` attribute contains indentification of the channel and is meant for internal
        use only (i.e. #multi_231). This attribute are usually only set by instance channels (see below).
        If no `id_name` is specified, cls.`id_name` will be cls.`name`.

    instance: `bool`
        Instanced channels are deleted when all players have left;
        this is useful for things like multiplayer, spectator, etc.
    """
    __slots__ = ('name', 'topic', 'players',
                 'read_priv', 'write_priv',
                 'auto_join', 'instance', 'id_name')

    def __init__(self, name: str, topic: str,
                 id_name: str = None,
                 read_priv: Privileges = Privileges.Normal,
                 write_priv: Privileges = Privileges.Normal,
                 auto_join: bool = True,
                 instance: bool = False) -> None:
        self.name = name
        self.topic = topic
        self.read_priv = read_priv
        self.write_priv = write_priv
        self.auto_join = auto_join
        self.instance = instance

        if id_name is None:
            self.id_name = self.name
        else:
            self.id_name = id_name

        self.players: list['Player'] = set()


    @property
    def basic_info(self) -> tuple[str, str, int]:
        return (self.name, self.topic, len(self))

    def __repr__(self) -> str:
        return f'<{self.name}>'

    def __contains__(self, p: 'Player') -> bool:
        return p in self.players

    def __len__(self) -> int:
        return len(self.players)

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
        self.players.add(p)

    def remove(self, p: 'Player') -> None:
        """Remove `p` from the channel's players."""
        self.players.remove(p)

        if len(self) == 0 and self.instance:
            # if it's an instance channel and this
            # is the last member leaving, just remove
            # the channel from the global list.
            glob.channels.remove(self)

    def enqueue(self, data: bytes, immune: tuple[int, ...] = ()) -> None:
        """Enqueue `data` to all connected clients not in `immune`."""
        for p in self.players:
            if p.id not in immune:
                p.enqueue(data)
