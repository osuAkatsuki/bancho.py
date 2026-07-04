from __future__ import annotations

from types import SimpleNamespace

from app.constants.privileges import Privileges
from app.services.visibility import can_view_player

VISIBLE = int(Privileges.UNRESTRICTED | Privileges.VERIFIED)
UNVERIFIED = int(Privileges.UNRESTRICTED)
RESTRICTED = int(Privileges.VERIFIED)
STAFF = int(Privileges.UNRESTRICTED | Privileges.VERIFIED | Privileges.ADMINISTRATOR)


def _viewer(id: int, priv: int) -> SimpleNamespace:
    return SimpleNamespace(id=id, priv=priv)


def test_public_players_are_visible_to_everyone() -> None:
    assert can_view_player(viewer=None, target_id=1, target_priv=VISIBLE)
    assert can_view_player(viewer=_viewer(2, VISIBLE), target_id=1, target_priv=VISIBLE)


def test_hidden_players_are_invisible_to_anonymous_viewers() -> None:
    assert not can_view_player(viewer=None, target_id=1, target_priv=UNVERIFIED)
    assert not can_view_player(viewer=None, target_id=1, target_priv=RESTRICTED)


def test_hidden_players_are_invisible_to_other_normal_players() -> None:
    viewer = _viewer(2, VISIBLE)
    assert not can_view_player(viewer=viewer, target_id=1, target_priv=UNVERIFIED)
    assert not can_view_player(viewer=viewer, target_id=1, target_priv=RESTRICTED)


def test_hidden_players_can_see_themselves() -> None:
    assert can_view_player(
        viewer=_viewer(1, UNVERIFIED),
        target_id=1,
        target_priv=UNVERIFIED,
    )
    assert can_view_player(
        viewer=_viewer(1, RESTRICTED),
        target_id=1,
        target_priv=RESTRICTED,
    )


def test_staff_can_see_hidden_players() -> None:
    viewer = _viewer(2, STAFF)
    assert can_view_player(viewer=viewer, target_id=1, target_priv=UNVERIFIED)
    assert can_view_player(viewer=viewer, target_id=1, target_priv=RESTRICTED)
