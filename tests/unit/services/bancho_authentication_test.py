from __future__ import annotations

from types import SimpleNamespace

import bcrypt

from app.services.bancho import BanchoAuthenticationService


class _FakeUsers:
    def __init__(self, user: object | None) -> None:
        self.user = user
        self.calls: list[dict[str, object]] = []

    async def fetch_one(
        self,
        *,
        name: str,
        fetch_all_fields: bool = False,
    ) -> object | None:
        self.calls.append(
            {
                "name": name,
                "fetch_all_fields": fetch_all_fields,
            },
        )
        return self.user


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
    service = BanchoAuthenticationService(
        users=_FakeUsers(None),
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
    service = BanchoAuthenticationService(
        users=_FakeUsers(None),
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
    service = BanchoAuthenticationService(
        users=_FakeUsers(None),
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
    service = BanchoAuthenticationService(
        users=_FakeUsers(None),
        online_players=_FakeOnlinePlayers(player),
        password_cache={},
    )

    authenticated_player = await service.authenticate_online_player(
        username="cmyui",
        password_md5="password-md5",
    )

    assert authenticated_player is None


async def test_authenticate_login_credentials_returns_user_from_cached_password() -> (
    None
):
    user = SimpleNamespace(pw_bcrypt="bcrypt-hash")
    users = _FakeUsers(user)
    service = BanchoAuthenticationService(
        users=users,
        online_players=_FakeOnlinePlayers(None),
        password_cache={b"bcrypt-hash": b"password-md5"},
    )

    authenticated_user = await service.authenticate_login_credentials(
        "cmyui",
        b"password-md5",
    )

    assert authenticated_user is user
    assert users.calls == [{"name": "cmyui", "fetch_all_fields": True}]


async def test_authenticate_login_credentials_rejects_wrong_cached_password() -> None:
    user = SimpleNamespace(pw_bcrypt="bcrypt-hash")
    service = BanchoAuthenticationService(
        users=_FakeUsers(user),
        online_players=_FakeOnlinePlayers(None),
        password_cache={b"bcrypt-hash": b"password-md5"},
    )

    authenticated_user = await service.authenticate_login_credentials(
        "cmyui",
        b"wrong-md5",
    )

    assert authenticated_user is None


async def test_authenticate_login_credentials_caches_valid_bcrypt_password() -> None:
    password_md5 = b"password-md5"
    password_bcrypt = bcrypt.hashpw(password_md5, bcrypt.gensalt(rounds=4))
    user = SimpleNamespace(pw_bcrypt=password_bcrypt.decode())
    password_cache: dict[bytes, bytes] = {}
    service = BanchoAuthenticationService(
        users=_FakeUsers(user),
        online_players=_FakeOnlinePlayers(None),
        password_cache=password_cache,
    )

    authenticated_user = await service.authenticate_login_credentials(
        "cmyui",
        password_md5,
    )

    assert authenticated_user is user
    assert password_cache == {password_bcrypt: password_md5}


async def test_authenticate_login_credentials_rejects_missing_user() -> None:
    service = BanchoAuthenticationService(
        users=_FakeUsers(None),
        online_players=_FakeOnlinePlayers(None),
        password_cache={},
    )

    authenticated_user = await service.authenticate_login_credentials(
        "cmyui",
        b"password-md5",
    )

    assert authenticated_user is None
