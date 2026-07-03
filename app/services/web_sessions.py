from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from app.repositories.users import User
from app.repositories.users import UsersRepository
from app.services.bancho import BanchoAuthenticationService

WEB_SESSION_EXPIRY_SECONDS = 60 * 60 * 24 * 30  # 30 days


class SessionTokenStore(Protocol):
    async def set_with_expiry(
        self,
        key: str,
        value: str,
        expiry_seconds: int,
    ) -> None: ...

    async def get(self, key: str) -> str | None: ...

    async def delete(self, key: str) -> None: ...


@dataclass(frozen=True)
class WebSession:
    token: str
    user_id: int


def _session_key(token: str) -> str:
    return f"bancho:web_sessions:{token}"


@dataclass(frozen=True)
class WebSessionsService:
    authentication: BanchoAuthenticationService
    users: UsersRepository
    token_store: SessionTokenStore
    generate_token: Callable[[], str]

    async def login(self, *, username: str, password: str) -> WebSession | None:
        """Create a web session for a player, given valid credentials."""
        # bancho.py stores bcrypt hashes of the md5 of the plaintext
        # password, since that's what the osu! client sends at login.
        password_md5 = hashlib.md5(password.encode()).hexdigest().encode()

        user = await self.authentication.authenticate_login_credentials(
            username,
            password_md5,
        )
        if user is None:
            return None

        token = self.generate_token()
        await self.token_store.set_with_expiry(
            _session_key(token),
            str(user.id),
            WEB_SESSION_EXPIRY_SECONDS,
        )
        return WebSession(token=token, user_id=user.id)

    async def fetch_session_user(self, token: str) -> User | None:
        """Fetch the player that a session token belongs to, if valid."""
        user_id = await self.token_store.get(_session_key(token))
        if user_id is None:
            return None

        return await self.users.fetch_one(id=int(user_id))

    async def logout(self, token: str) -> None:
        await self.token_store.delete(_session_key(token))
