from __future__ import annotations

import pytest

import app.packets
import app.state.sessions
from app.constants.privileges import Privileges
from app.objects.collections import Players
from app.objects.player import Player


def _player(*, id: int, name: str, priv: Privileges) -> Player:
    return Player(
        id=id,
        name=name,
        priv=priv,
        pw_bcrypt=None,
        token=Player.generate_token(),
    )


def test_logout_fully_removes_player_from_session_indexes() -> None:
    # regression test: logout() used to invalidate the token before
    # removing the player, corrupting the collection's token index.
    players = Players()
    original_players = app.state.sessions.players
    app.state.sessions.players = players
    try:
        player = _player(
            id=3,
            name="test player",
            priv=Privileges.UNRESTRICTED | Privileges.VERIFIED,
        )
        token = player.token
        players.append(player)

        assert players.get(token=token) is player
        assert players.get(id=player.id) is player
        assert players.get(name=player.name) is player

        player.logout()

        assert player.token == ""
        assert player not in players
        assert players.get(token=token) is None
        assert players.get(id=player.id) is None
        assert players.get(name=player.name) is None
    finally:
        app.state.sessions.players = original_players


@pytest.mark.parametrize(
    ("priv", "expected_packet"),
    [
        (
            Privileges.UNRESTRICTED | Privileges.VERIFIED,
            app.packets.logout(3),
        ),
        (Privileges.VERIFIED, None),
    ],
)
def test_logout_only_broadcasts_unrestricted_players(
    priv: Privileges,
    expected_packet: bytes | None,
) -> None:
    players = Players()
    original_players = app.state.sessions.players
    app.state.sessions.players = players
    try:
        player = _player(id=3, name="departing player", priv=priv)
        observer = _player(
            id=4,
            name="remaining player",
            priv=Privileges.UNRESTRICTED | Privileges.VERIFIED,
        )
        players.append(player)
        players.append(observer)

        player.logout()

        assert observer.dequeue() == expected_packet
        assert observer in players
    finally:
        app.state.sessions.players = original_players
