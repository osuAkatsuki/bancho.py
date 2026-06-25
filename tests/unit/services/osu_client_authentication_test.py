from __future__ import annotations

from types import SimpleNamespace

from app.services.osu_client_authentication import OsuClientAuthenticationService


class _FakeOnlinePlayers:
    def __init__(self, player: object | None) -> None:
        self.player = player
        self.calls: list[dict[str, object | None]] = []

    def get(
        self,
        token: str | None = None,
        id: int | None = None,
        name: str | None = None,
    ) -> object | None:
        self.calls.append({"token": token, "id": id, "name": name})
        return self.player


async def test_authenticate_online_player_returns_matching_player() -> None:
    player = SimpleNamespace(pw_bcrypt=b"bcrypt-hash")
    online_players = _FakeOnlinePlayers(player)
    service = OsuClientAuthenticationService(
        online_players=online_players,
        password_cache={b"bcrypt-hash": b"password-md5"},
    )

    authenticated_player = await service.authenticate_online_player(
        username="cmyui",
        password_md5="password-md5",
    )

    assert authenticated_player is player
    assert online_players.calls == [{"token": None, "id": None, "name": "cmyui"}]


async def test_authenticate_online_player_rejects_missing_player() -> None:
    online_players = _FakeOnlinePlayers(None)
    service = OsuClientAuthenticationService(
        online_players=online_players,
        password_cache={},
    )

    authenticated_player = await service.authenticate_online_player(
        username="cmyui",
        password_md5="password-md5",
    )

    assert authenticated_player is None


async def test_authenticate_online_player_rejects_wrong_password_hash() -> None:
    player = SimpleNamespace(pw_bcrypt=b"bcrypt-hash")
    service = OsuClientAuthenticationService(
        online_players=_FakeOnlinePlayers(player),
        password_cache={b"bcrypt-hash": b"password-md5"},
    )

    authenticated_player = await service.authenticate_online_player(
        username="cmyui",
        password_md5="wrong-md5",
    )

    assert authenticated_player is None


async def test_authenticate_online_player_rejects_missing_cached_password_hash() -> (
    None
):
    player = SimpleNamespace(pw_bcrypt=b"bcrypt-hash")
    service = OsuClientAuthenticationService(
        online_players=_FakeOnlinePlayers(player),
        password_cache={},
    )

    authenticated_player = await service.authenticate_online_player(
        username="cmyui",
        password_md5="password-md5",
    )

    assert authenticated_player is None
