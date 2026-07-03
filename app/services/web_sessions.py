from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass

from app.repositories.users import User
from app.repositories.users import UsersRepository
from app.repositories.web_sessions import WebSessionsRepository
from app.services.bancho import BanchoAuthenticationService

WEB_SESSION_EXPIRY_SECONDS = 60 * 60 * 24 * 30  # 30 days


@dataclass(frozen=True)
class WebSession:
    token: str
    user: User


@dataclass(frozen=True)
class WebSessionsService:
    authentication: BanchoAuthenticationService
    users: UsersRepository
    web_sessions: WebSessionsRepository
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
        await self.web_sessions.create(
            token,
            user.id,
            WEB_SESSION_EXPIRY_SECONDS,
        )
        return WebSession(token=token, user=user)

    async def fetch_session_user(self, token: str) -> User | None:
        """Fetch the player that a session token belongs to, if valid."""
        user_id = await self.web_sessions.fetch_user_id(token)
        if user_id is None:
            return None

        return await self.users.fetch_one(id=user_id)

    async def logout(self, token: str) -> None:
        await self.web_sessions.delete(token)
