"""Shared visibility policy for player-owned resources.

Hidden (restricted or unverified) players -- and everything they own:
profiles, stats, statuses, scores, replays, favourites -- are visible
only to staff and to the players themselves. Endpoints return 404 for
hidden resources so that their existence is not revealed.

The same rules are applied in SQL for listing queries (e.g. player
search and score listings), where filtering in the database is cheaper
than fetching rows only to discard them.
"""

from __future__ import annotations

from typing import Protocol

from app.constants.privileges import Privileges

PUBLIC_PLAYER_MASK = Privileges.UNRESTRICTED | Privileges.VERIFIED


class PlayerIdentity(Protocol):
    """Any object identifying a player; both the repository `User` and
    the in-game session `Player` satisfy this."""

    @property
    def id(self) -> int: ...

    @property
    def priv(self) -> int: ...


def can_view_player(
    *,
    viewer: PlayerIdentity | None,
    target_id: int,
    target_priv: int,
) -> bool:
    """Whether `viewer` (None = anonymous) may see the player-owned
    resources of the target player."""
    if target_priv & PUBLIC_PLAYER_MASK.value == PUBLIC_PLAYER_MASK.value:
        return True
    if viewer is None:
        return False
    return viewer.id == target_id or viewer.priv & Privileges.STAFF.value != 0
