from __future__ import annotations

import app.state.sessions
from app.constants.privileges import Privileges
from app.objects.collections import Players
from app.objects.player import Player


def test_logout_fully_removes_player_from_session_indexes() -> None:
    # regression test: logout() used to invalidate the token before
    # removing the player, corrupting the collection's token index.
    players = Players()
    original_players = app.state.sessions.players
    app.state.sessions.players = players
    try:
        player = Player(
            id=3,
            name="test player",
            priv=Privileges.UNRESTRICTED | Privileges.VERIFIED,
            pw_bcrypt=None,
            token=Player.generate_token(),
        )
        token = player.token
        players.append(player)

        player.logout()

        assert player.token == ""
        assert player not in players
        assert players.get(token=token) is None
        assert players.get(id=player.id) is None
        assert players.get(name=player.name) is None
    finally:
        app.state.sessions.players = original_players
