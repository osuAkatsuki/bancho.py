from __future__ import annotations

from collections.abc import Iterable
from collections.abc import Iterator
from collections.abc import Sequence
from typing import TYPE_CHECKING
from typing import Any

import app.settings
from app.constants.privileges import Privileges
from app.logging import log
from app.utils import make_safe_name

if TYPE_CHECKING:
    from app.objects.channel import Channel
    from app.objects.match import Match
    from app.objects.player import Player


class Channels(list["Channel"]):
    """The currently active chat channels on the server."""

    def __iter__(self) -> Iterator[Channel]:
        return super().__iter__()

    def __contains__(self, o: object) -> bool:
        """Check whether internal list contains `o`."""
        # Allow string to be passed to compare vs. name.
        if isinstance(o, str):
            return o in (chan.name for chan in self)
        else:
            return super().__contains__(o)

    def __repr__(self) -> str:
        # XXX: we use the "real" name, aka
        # #multi_1 instead of #multiplayer
        # #spect_1 instead of #spectator.
        return f'[{", ".join(c.real_name for c in self)}]'

    def get_by_name(self, name: str) -> Channel | None:
        """Get a channel from the list by `name`."""
        for channel in self:
            if channel.real_name == name:
                return channel

        return None

    def append(self, channel: Channel) -> None:
        """Append `channel` to the list."""
        super().append(channel)

        if app.settings.DEBUG:
            log(f"{channel} added to channels list.")

    def extend(self, channels: Iterable[Channel]) -> None:
        """Extend the list with `channels`."""
        super().extend(channels)

        if app.settings.DEBUG:
            log(f"{channels} added to channels list.")

    def remove(self, channel: Channel) -> None:
        """Remove `channel` from the list."""
        super().remove(channel)

        if app.settings.DEBUG:
            log(f"{channel} removed from channels list.")


class Matches(list["Match | None"]):
    """The currently active multiplayer matches on the server."""

    def __init__(self) -> None:
        MAX_MATCHES = 64  # TODO: refactor this out of existence
        super().__init__([None] * MAX_MATCHES)

    def __iter__(self) -> Iterator[Match | None]:
        return super().__iter__()

    def __repr__(self) -> str:
        return f'[{", ".join(match.name for match in self if match)}]'

    def get_free(self) -> int | None:
        """Return the first free match id from `self`."""
        for idx, match in enumerate(self):
            if match is None:
                return idx

        return None

    def remove(self, match: Match | None) -> None:
        """Remove `match` from the list."""
        for i, _m in enumerate(self):
            if match is _m:
                self[i] = None
                break

        if app.settings.DEBUG:
            log(f"{match} removed from matches list.")


class Players(list["Player"]):
    """The currently active players on the server."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._by_token: dict[str, Player] = {}
        self._by_id: dict[int, Player] = {}
        self._by_name: dict[str, Player] = {}

    def __iter__(self) -> Iterator[Player]:
        return super().__iter__()

    def __contains__(self, player: object) -> bool:
        if isinstance(player, str):
            return make_safe_name(player) in self._by_name
        else:
            return super().__contains__(player)

    def __repr__(self) -> str:
        return f'[{", ".join(map(repr, self))}]'

    @property
    def ids(self) -> set[int]:
        """Return a set of the current ids in the list."""
        return {p.id for p in self}

    @property
    def staff(self) -> set[Player]:
        """Return a set of the current staff online."""
        return {p for p in self if p.priv & Privileges.STAFF}

    @property
    def restricted(self) -> set[Player]:
        """Return a set of the current restricted players."""
        return {p for p in self if not p.priv & Privileges.UNRESTRICTED}

    @property
    def unrestricted(self) -> set[Player]:
        """Return a set of the current unrestricted players."""
        return {p for p in self if p.priv & Privileges.UNRESTRICTED}

    def enqueue(self, data: bytes, immune: Sequence[Player] = []) -> None:
        """Enqueue `data` to all players, except for those in `immune`."""
        for player in self:
            if player not in immune:
                player.enqueue(data)

    def get(
        self,
        token: str | None = None,
        id: int | None = None,
        name: str | None = None,
    ) -> Player | None:
        """Get a player by token, id, or name from cache."""
        if token is not None:
            return self._by_token.get(token)
        elif id is not None:
            return self._by_id.get(id)
        elif name is not None:
            return self._by_name.get(make_safe_name(name))
        return None

    def append(self, player: Player) -> None:
        """Append `player` to the list."""
        if player in self:
            if app.settings.DEBUG:
                log(f"{player} double-added to global player list?")
            return

        super().append(player)
        self._by_token[player.token] = player
        self._by_id[player.id] = player
        self._by_name[player.safe_name] = player

    def remove(self, player: Player) -> None:
        """Remove `player` from the list."""
        if player not in self:
            if app.settings.DEBUG:
                log(f"{player} removed from player list when not online?")
            return

        super().remove(player)
        del self._by_token[player.token]
        del self._by_id[player.id]
        del self._by_name[player.safe_name]
