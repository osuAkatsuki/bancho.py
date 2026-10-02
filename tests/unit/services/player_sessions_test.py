from __future__ import annotations

import pytest

import app.packets
from app.constants.privileges import Privileges
from app.objects.collections import Channels
from app.objects.collections import Matches
from app.objects.collections import Players
from app.objects.player import Player
from app.services.player_sessions import PlayerSessionService


def _player(*, id: int, name: str, priv: Privileges) -> Player:
    return Player(
        id=id,
        name=name,
        priv=priv,
        pw_bcrypt=None,
        token=Player.generate_token(),
    )


def _service(players: Players, bot: Player) -> PlayerSessionService:
    return PlayerSessionService(
        players=players,
        channels=Channels(),
        matches=Matches(),
        bot=bot,
        decrement_online_players=lambda: None,
        debug=False,
    )


def test_logout_fully_removes_player_from_session_indexes() -> None:
    # Regression test: logout used to invalidate the token before removing the
    # player, corrupting the collection's token index.
    players = Players()
    bot = _player(id=1, name="bot", priv=Privileges.UNRESTRICTED)
    player = _player(
        id=3,
        name="test player",
        priv=Privileges.UNRESTRICTED | Privileges.VERIFIED,
    )
    token = player.token
    players.append(bot)
    players.append(player)

    assert players.get(token=token) is player
    assert players.get(id=player.id) is player
    assert players.get(name=player.name) is player

    _service(players, bot).logout(player)

    assert player.token == ""
    assert player not in players
    assert players.get(token=token) is None
    assert players.get(id=player.id) is None
    assert players.get(name=player.name) is None


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
    bot = _player(id=1, name="bot", priv=Privileges.UNRESTRICTED)
    player = _player(id=3, name="departing player", priv=priv)
    observer = _player(
        id=4,
        name="remaining player",
        priv=Privileges.UNRESTRICTED | Privileges.VERIFIED,
    )
    players.append(bot)
    players.append(player)
    players.append(observer)

    _service(players, bot).logout(player)

    assert observer.dequeue() == expected_packet
    assert observer in players
