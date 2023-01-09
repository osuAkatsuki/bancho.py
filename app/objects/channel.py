from __future__ import annotations

from typing import Sequence
from typing import TYPE_CHECKING

import app.packets
import app.state
from app.constants.privileges import Privileges

if TYPE_CHECKING:
    from app.objects.player import Player

__all__ = ("Channel",)


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

    def __init__(
        self,
        name: str,
        topic: str,
        read_priv: Privileges = Privileges.UNRESTRICTED,
        write_priv: Privileges = Privileges.UNRESTRICTED,
        auto_join: bool = True,
        instance: bool = False,
    ) -> None:
        # TODO: think of better names than `_name` and `name`
        self._name = name  # 'real' name ('#{multi/spec}_{id}')

        if self._name.startswith("#spec_"):
            self.name = "#spectator"
        elif self._name.startswith("#multi_"):
            self.name = "#multiplayer"
        else:
            self.name = self._name

        self.topic = topic
        self.read_priv = read_priv
        self.write_priv = write_priv
        self.auto_join = auto_join
        self.instance = instance

        self.players: list[Player] = []

    def __repr__(self) -> str:
        return f"<{self._name}>"

    def __contains__(self, player: Player) -> bool:
        return player in self.players

    # XXX: should this be cached differently?

    def can_read(self, priv: Privileges) -> bool:
        if not self.read_priv:
            return True

        return priv & self.read_priv != 0

    def can_write(self, priv: Privileges) -> bool:
        if not self.write_priv:
            return True

        return priv & self.write_priv != 0

    def send(self, msg: str, sender: Player, to_self: bool = False) -> None:
        """Enqueue `msg` to all appropriate clients from `sender`."""
        data = app.packets.send_message(
            sender=sender.name,
            msg=msg,
            recipient=self.name,
            sender_id=sender.id,
        )

        for player in self.players:
            if sender.id not in player.blocks and (to_self or player.id != sender.id):
                player.enqueue(data)

    def send_bot(self, msg: str) -> None:
        """Enqueue `msg` to all connected clients from bot."""
        bot = app.state.sessions.bot

        msg_len = len(msg)

        if msg_len >= 31979:  # TODO ??????????
            msg = f"message would have crashed games ({msg_len} chars)"

        self.enqueue(
            app.packets.send_message(
                sender=bot.name,
                msg=msg,
                recipient=self.name,
                sender_id=bot.id,
            ),
        )

    def send_selective(
        self,
        msg: str,
        sender: Player,
        recipients: set[Player],
    ) -> None:
        """Enqueue `sender`'s `msg` to `recipients`."""
        for player in recipients:
            if player in self:
                player.send(msg, sender=sender, chan=self)

    def append(self, player: Player) -> None:
        """Add `player` to the channel's players."""
        self.players.append(player)

    def remove(self, player: Player) -> None:
        """Remove `player` from the channel's players."""
        self.players.remove(player)

        if not self.players and self.instance:
            # if it's an instance channel and this
            # is the last member leaving, just remove
            # the channel from the global list.
            app.state.sessions.channels.remove(self)

    def enqueue(self, data: bytes, immune: Sequence[int] = []) -> None:
        """Enqueue `data` to all connected clients not in `immune`."""
        for player in self.players:
            if player.id not in immune:
                player.enqueue(data)
