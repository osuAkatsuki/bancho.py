from __future__ import annotations

from typing import TYPE_CHECKING

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
        read_priv: int = Privileges.UNRESTRICTED,
        write_priv: int = Privileges.UNRESTRICTED,
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

    def __contains__(self, p: Player) -> bool:
        return p in self.players
