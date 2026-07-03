from __future__ import annotations

import hashlib
from types import SimpleNamespace

import app.services.web_sessions as web_sessions


class _FakeAuthenticationService:
    def __init__(self, user: SimpleNamespace | None) -> None:
        self.user = user
        self.calls: list[tuple[str, bytes]] = []

    async def authenticate_login_credentials(
        self,
        username: str,
        untrusted_password: bytes,
    ) -> SimpleNamespace | None:
        self.calls.append((username, untrusted_password))
        return self.user


class _FakeUsersRepository:
    def __init__(self, user: SimpleNamespace | None) -> None:
        self.user = user

    async def fetch_one(self, id: int | None = None) -> SimpleNamespace | None:
        return self.user if self.user is not None and self.user.id == id else None


class _FakeWebSessionsRepository:
    def __init__(self) -> None:
        self.sessions: dict[str, int] = {}

    async def create(
        self,
        token: str,
        user_id: int,
        expiry_seconds: int,
    ) -> None:
        self.sessions[token] = user_id

    async def fetch_user_id(self, token: str) -> int | None:
        return self.sessions.get(token)

    async def delete(self, token: str) -> None:
        self.sessions.pop(token, None)


def _service(
    *,
    user: SimpleNamespace | None,
    web_sessions_repo: _FakeWebSessionsRepository | None = None,
) -> web_sessions.WebSessionsService:
    return web_sessions.WebSessionsService(
        authentication=_FakeAuthenticationService(user),
        users=_FakeUsersRepository(user),
        web_sessions=(
            web_sessions_repo
            if web_sessions_repo is not None
            else _FakeWebSessionsRepository()
        ),
        generate_token=lambda: "test-token",
    )


async def test_web_sessions_login_stores_a_session_token() -> None:
    web_sessions_repo = _FakeWebSessionsRepository()
    user = SimpleNamespace(id=3, name="cmyui")
    service = _service(user=user, web_sessions_repo=web_sessions_repo)

    session = await service.login(username="cmyui", password="myPassword321$")

    assert session == web_sessions.WebSession(token="test-token", user=user)
    assert web_sessions_repo.sessions == {"test-token": 3}

    # the authentication layer receives the md5 of the plaintext password
    expected_md5 = hashlib.md5(b"myPassword321$").hexdigest().encode()
    assert service.authentication.calls == [("cmyui", expected_md5)]


async def test_web_sessions_login_rejects_invalid_credentials() -> None:
    web_sessions_repo = _FakeWebSessionsRepository()
    service = _service(user=None, web_sessions_repo=web_sessions_repo)

    session = await service.login(username="cmyui", password="wrong")

    assert session is None
    assert web_sessions_repo.sessions == {}


async def test_web_sessions_fetch_session_user_roundtrip() -> None:
    user = SimpleNamespace(id=3, name="cmyui")
    service = _service(user=user)

    session = await service.login(username="cmyui", password="myPassword321$")
    assert session is not None

    assert await service.fetch_session_user(session.token) is user
    assert await service.fetch_session_user("unknown-token") is None


async def test_web_sessions_logout_invalidates_the_token() -> None:
    user = SimpleNamespace(id=3, name="cmyui")
    service = _service(user=user)

    session = await service.login(username="cmyui", password="myPassword321$")
    assert session is not None

    await service.logout(session.token)
    assert await service.fetch_session_user(session.token) is None
