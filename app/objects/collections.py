# TODO: there is still a lot of inconsistency
# in a lot of these classes; needs refactor.
from __future__ import annotations

from typing import Any
from typing import Iterable
from typing import Iterator
from typing import Optional
from typing import overload
from typing import Sequence
from typing import Union

import app.settings
import app.state
import app.utils
from app.constants.privileges import Privileges
from app.logging import log
from app.objects.channel import Channel
from app.objects.clan import Clan
from app.objects.match import Match
from app.objects.player import Player
from app.utils import make_safe_name

__all__ = (
    "Channels",
    "Matches",
    "Players",
    "Clans",
)

# TODO: decorator for these collections which automatically
# adds debugging to their append/remove/insert/extend methods.


class Channels(list[Channel]):
    """The currently active chat channels on the server."""

    def __iter__(self) -> Iterator[Channel]:
        return super().__iter__()

    def __contains__(self, o: Union[Channel, str]) -> bool:
        """Check whether internal list contains `o`."""
        # Allow string to be passed to compare vs. name.
        if isinstance(o, str):
            return o in (chan.name for chan in self)
        else:
            return super().__contains__(o)

    @overload
    def __getitem__(self, index: int) -> Channel:
        ...

    @overload
    def __getitem__(self, index: str) -> Channel:
        ...

    @overload
    def __getitem__(self, index: slice) -> list[Channel]:
        ...

    def __getitem__(
        self,
        index: Union[int, slice, str],
    ) -> Union[Channel, list[Channel]]:
        # XXX: can be either a string (to get by name),
        # or a slice, for indexing the internal array.
        if isinstance(index, str):
            return self.get_by_name(index)  # type: ignore
        else:
            return super().__getitem__(index)

    def __repr__(self) -> str:
        # XXX: we use the "real" name, aka
        # #multi_1 instead of #multiplayer
        # #spect_1 instead of #spectator.
        return f'[{", ".join(c._name for c in self)}]'

    def get_by_name(self, name: str) -> Optional[Channel]:
        """Get a channel from the list by `name`."""
        for c in self:
            if c._name == name:
                return c

        return None

    def append(self, c: Channel) -> None:
        """Append `c` to the list."""
        super().append(c)

        if app.settings.DEBUG:
            log(f"{c} added to channels list.")

    def extend(self, cs: Iterable[Channel]) -> None:
        """Extend the list with `cs`."""
        super().extend(cs)

        if app.settings.DEBUG:
            log(f"{cs} added to channels list.")

    def remove(self, c: Channel) -> None:
        """Remove `c` from the list."""
        super().remove(c)

        if app.settings.DEBUG:
            log(f"{c} removed from channels list.")


class Matches(list[Optional[Match]]):
    """The currently active multiplayer matches on the server."""

    def __init__(self) -> None:
        super().__init__([None] * 64)  # TODO: customizability?

    def __iter__(self) -> Iterator[Optional[Match]]:
        return super().__iter__()

    def __repr__(self) -> str:
        return f'[{", ".join(match.name for match in self if match)}]'

    def get_free(self) -> Optional[int]:
        """Return the first free match id from `self`."""
        for idx, m in enumerate(self):
            if m is None:
                return idx

        return None

    def append(self, m: Match) -> bool:
        """Append `m` to the list."""
        if (free := self.get_free()) is not None:
            # set the id of the match to the lowest available free.
            m.id = free
            self[free] = m

            if app.settings.DEBUG:
                log(f"{m} added to matches list.")

            return True
        else:
            log(f"Match list is full! Could not add {m}.")
            return False

    # TODO: extend

    def remove(self, m: Match) -> None:
        """Remove `m` from the list."""
        for i, _m in enumerate(self):
            if m is _m:
                self[i] = None
                break

        if app.settings.DEBUG:
            log(f"{m} removed from matches list.")


class Players(list[Player]):
    """The currently active players on the server."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __iter__(self) -> Iterator[Player]:
        return super().__iter__()

    def __contains__(self, p: Union[Player, str]) -> bool:
        # allow us to either pass in the player
        # obj, or the player name as a string.
        if isinstance(p, str):
            return p in (player.name for player in self)
        else:
            return super().__contains__(p)

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
        return {p for p in self if not p.priv & Privileges.NORMAL}

    @property
    def unrestricted(self) -> set[Player]:
        """Return a set of the current unrestricted players."""
        return {p for p in self if p.priv & Privileges.NORMAL}

    def enqueue(self, data: bytes, immune: Sequence[Player] = []) -> None:
        """Enqueue `data` to all players, except for those in `immune`."""
        for p in self:
            if p not in immune:
                p.enqueue(data)

    @staticmethod
    def _parse_attr(kwargs: dict[str, Any]) -> tuple[str, object]:
        """Get first matched attr & val from input kwargs. Used in get() methods."""
        for attr in ("token", "id", "name"):
            if (val := kwargs.pop(attr, None)) is not None:
                if attr == "name":
                    attr = "safe_name"
                    val = make_safe_name(val)

                return attr, val
        else:
            raise ValueError("Incorrect call to Players.get()")

    def get(self, **kwargs: object) -> Optional[Player]:
        """Get a player by token, id, or name from cache."""
        attr, val = self._parse_attr(kwargs)

        for p in self:
            if getattr(p, attr) == val:
                return p

        return None

    def append(self, p: Player) -> None:
        """Append `p` to the list."""
        if p in self:
            if app.settings.DEBUG:
                log(f"{p} double-added to global player list?")
            return

        super().append(p)

    def remove(self, p: Player) -> None:
        """Remove `p` from the list."""
        if p not in self:
            if app.settings.DEBUG:
                log(f"{p} removed from player list when not online?")
            return

        super().remove(p)


class Clans(list[Clan]):
    """The currently active clans on the server."""

    def __iter__(self) -> Iterator[Clan]:
        return super().__iter__()

    @overload
    def __getitem__(self, index: int) -> Clan:
        ...

    @overload
    def __getitem__(self, index: str) -> Clan:
        ...

    @overload
    def __getitem__(self, index: slice) -> list[Clan]:
        ...

    def __getitem__(self, index: Union[int, str, slice]):
        """Allow slicing by either a string (for name), or slice."""
        if isinstance(index, str):
            return self.get(name=index)
        else:
            return super().__getitem__(index)

    def __contains__(self, o: Union[Clan, str]) -> bool:
        """Check whether internal list contains `o`."""
        # Allow string to be passed to compare vs. name.
        if isinstance(o, str):
            return o in (clan.name for clan in self)
        else:
            return o in self

    def get(self, **kwargs: object) -> Optional[Clan]:
        """Get a clan by name, tag, or id."""
        for attr in ("name", "tag", "id"):
            if val := kwargs.pop(attr, None):
                break
        else:
            raise ValueError("Incorrect call to Clans.get()")

        for c in self:
            if getattr(c, attr) == val:
                return c

        return None

    def append(self, c: Clan) -> None:
        """Append `c` to the list."""
        super().append(c)

        if app.settings.DEBUG:
            log(f"{c} added to clans list.")

    def extend(self, cs: Iterable[Clan]) -> None:
        """Extend the list with `cs`."""
        super().extend(cs)

        if app.settings.DEBUG:
            log(f"{cs} added to clans list.")

    def remove(self, c: Clan) -> None:
        """Remove `m` from the list."""
        super().remove(c)

        if app.settings.DEBUG:
            log(f"{c} removed from clans list.")
