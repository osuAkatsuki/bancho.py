# TODO: there is still a lot of inconsistency
# in a lot of these classes; needs refactor.
from __future__ import annotations

from typing import Any
from typing import Iterable
from typing import Iterator
from typing import Optional
from typing import Sequence
from typing import Union

import app.settings
import app.state
import app.utils
from app.constants.privileges import Privileges
from app.logging import log
from app.objects.match import Match
from app.objects.player import Player
from app.utils import make_safe_name

__all__ = (
    "Matches",
    "Players",
)

# TODO: decorator for these collections which automatically
# adds debugging to their append/remove/insert/extend methods.


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
        return {p for p in self if not p.priv & Privileges.UNRESTRICTED}

    @property
    def unrestricted(self) -> set[Player]:
        """Return a set of the current unrestricted players."""
        return {p for p in self if p.priv & Privileges.UNRESTRICTED}

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
