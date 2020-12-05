# -*- coding: utf-8 -*-

from typing import TYPE_CHECKING
from constants.privileges import Privileges
from objects import glob
import packets

if TYPE_CHECKING:
    from objects.player import Player

__all__ = 'Channel',

class Channel:
    """A class to represent a chat channel.

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
                 'read', 'write',
                 'auto_join', 'instance')

    def __init__(self, name: str, topic: str,
                 read: Privileges = Privileges.Normal,
                 write: Privileges = Privileges.Normal,
                 auto_join: bool = True,
                 instance: bool = False,
                 *args, **kwargs) -> None:
        self._name = name # 'real' name ('#{multi/spec}_{id}')
        self.topic = topic
        self.read = read
        self.write = write
        self.auto_join = auto_join
        self.instance = instance

        self.players: list['Player'] = []

    @property
    def name(self) -> str:
        if self._name.startswith('#spec_'):
            return '#spectator'
        elif self._name.startswith('#multi_'):
            return '#multiplayer'

        return self._name

    @property
    def basic_info(self) -> tuple[str, str, int]:
        return (self.name, self.topic, len(self.players))

    def __repr__(self) -> str:
        return f'<{self._name}>'

    def __contains__(self, p: 'Player') -> bool:
        return p in self.players

    async def send(self, client: 'Player', msg: str,
                   to_self: bool = False) -> None:
        """Enqueue `client`'s `msg` to all connected clients."""
        self.enqueue(
            packets.sendMessage(
                client = client.name,
                msg = msg,
                target = self.name,
                client_id = client.id
            ),
            immune = () if to_self else (client.id,)
        )

    async def send_selective(self, client: 'Player', msg: str,
                             targets: list['Player']) -> None:
        """Enqueue `client`'s `msg` to `targets`."""
        for p in (t for t in targets if t in self):
            await p.send(client, msg, chan=self)

    def append(self, p: 'Player') -> None:
        """Add `p` to the channel's players."""
        self.players.append(p)

    async def remove(self, p: 'Player') -> None:
        """Remove `p` from the channel's players."""
        self.players.remove(p)

        if len(self.players) == 0 and self.instance:
            # if it's an instance channel and this
            # is the last member leaving, just remove
            # the channel from the global list.
            await glob.channels.remove(self)

    def enqueue(self, data: bytes, immune: tuple[int, ...] = ()) -> None:
        """Enqueue `data` to all connected clients not in `immune`."""
        for p in self.players:
            if p.id not in immune:
                p.enqueue(data)
