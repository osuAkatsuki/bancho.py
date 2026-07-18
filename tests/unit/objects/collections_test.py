from __future__ import annotations

from app.constants.privileges import Privileges
from app.objects.collections import Players
from app.objects.player import Player


def _player(*, id: int, name: str) -> Player:
    return Player(
        id=id,
        name=name,
        priv=Privileges.UNRESTRICTED | Privileges.VERIFIED,
        pw_bcrypt=None,
        token=Player.generate_token(),
    )


def test_players_append_and_remove_keep_lookup_indexes_synchronized() -> None:
    players = Players()
    player = _player(id=3, name="Test Player")

    players.append(player)

    assert players.get(token=player.token) is player
    assert players.get(id=player.id) is player
    assert players.get(name="test_player") is player

    players.remove(player)

    assert player not in players
    assert players.get(token=player.token) is None
    assert players.get(id=player.id) is None
    assert players.get(name=player.name) is None


def test_players_enqueue_respects_immune_players() -> None:
    players = Players()
    recipient = _player(id=3, name="recipient")
    immune = _player(id=4, name="immune")
    players.append(recipient)
    players.append(immune)

    players.enqueue(b"broadcast", immune=[immune])

    assert recipient.dequeue() == b"broadcast"
    assert immune.dequeue() is None
