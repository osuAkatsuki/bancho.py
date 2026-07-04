from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

import bcrypt

from app._typing import UNSET
from app._typing import _UnsetSentinel
from app.constants.countries import ISO_COUNTRY_CODES
from app.constants.privileges import Privileges
from app.objects.player import Player
from app.repositories.leaderboard_ranks import LeaderboardRanksRepository
from app.repositories.stats import StatsRepository
from app.repositories.users import User
from app.repositories.users import UsersRepository
from app.services.accounts import validate_password
from app.services.accounts import validate_username

MAX_USERPAGE_LENGTH = 2048  # users.userpage_content column size


class OnlinePlayers(Protocol):
    def get(
        self,
        token: str | None = None,
        id: int | None = None,
        name: str | None = None,
    ) -> Player | None: ...


class AuthenticationService(Protocol):
    async def authenticate_login_credentials(
        self,
        username: str,
        untrusted_password: bytes,
    ) -> User | None: ...


class ProfileUpdateErrors(dict[str, list[str]]):
    pass


class PasswordChangeResultCode(StrEnum):
    OK = "ok"
    INCORRECT_CURRENT_PASSWORD = "incorrect_current_password"
    VALIDATION_FAILED = "validation_failed"


@dataclass(frozen=True)
class PasswordChangeResult:
    code: PasswordChangeResultCode
    errors: list[str] | None = None


@dataclass(frozen=True)
class AccountSettingsService:
    users: UsersRepository
    stats: StatsRepository
    leaderboard_ranks: LeaderboardRanksRepository
    authentication: AuthenticationService
    online_players: OnlinePlayers
    password_cache: dict[bytes, bytes]
    disallowed_names: Sequence[str]
    disallowed_passwords: Sequence[str]

    async def validate_profile_update(
        self,
        user: User,
        *,
        username: str | _UnsetSentinel = UNSET,
        country: str | _UnsetSentinel = UNSET,
        userpage_content: str | None | _UnsetSentinel = UNSET,
    ) -> ProfileUpdateErrors:
        errors = ProfileUpdateErrors()

        if isinstance(username, str) and username != user.name:
            username_errors = validate_username(username, self.disallowed_names)
            if username_errors:
                errors["username"] = username_errors
            elif await self.users.fetch_one(name=username):
                errors["username"] = ["Username already taken by another player."]

        if isinstance(country, str) and country not in ISO_COUNTRY_CODES:
            errors["country"] = ["Invalid country code."]

        if isinstance(userpage_content, str):
            if len(userpage_content) > MAX_USERPAGE_LENGTH:
                errors["userpage_content"] = [
                    f"Must be at most {MAX_USERPAGE_LENGTH} characters in length.",
                ]

        return errors

    async def update_profile(
        self,
        user: User,
        *,
        username: str | _UnsetSentinel = UNSET,
        country: str | _UnsetSentinel = UNSET,
        preferred_mode: int | _UnsetSentinel = UNSET,
        userpage_content: str | None | _UnsetSentinel = UNSET,
    ) -> User:
        """Apply a validated profile update, keeping the game server's
        session cache and the redis country leaderboards consistent."""
        updated_user = await self.users.partial_update(
            id=user.id,
            name=username,
            country=country,
            preferred_mode=preferred_mode,
            userpage_content=userpage_content,
        )
        assert updated_user is not None

        # the game server caches profile data in memory for online players
        online_player = self.online_players.get(id=user.id)
        if online_player is not None:
            if isinstance(username, str):
                online_player.name = username
            if isinstance(country, str):
                online_player.geoloc["country"]["acronym"] = country

        # a country change moves the player between country leaderboards
        if isinstance(country, str) and country != user.country:
            is_unrestricted = user.priv & Privileges.UNRESTRICTED != 0
            for stat in await self.stats.fetch_many(player_id=user.id):
                await self.leaderboard_ranks.remove_from_country_leaderboard(
                    user.id,
                    stat.mode,
                    user.country,
                )
                if is_unrestricted:
                    await self.leaderboard_ranks.add_to_country_leaderboard(
                        user.id,
                        stat.mode,
                        country,
                        pp=stat.pp,
                    )

        return updated_user

    async def change_password(
        self,
        user: User,
        *,
        current_password: str,
        new_password: str,
    ) -> PasswordChangeResult:
        current_password_md5 = (
            hashlib.md5(current_password.encode()).hexdigest().encode()
        )
        authenticated = await self.authentication.authenticate_login_credentials(
            username=user.name,
            untrusted_password=current_password_md5,
        )
        if authenticated is None:
            return PasswordChangeResult(
                code=PasswordChangeResultCode.INCORRECT_CURRENT_PASSWORD,
            )

        errors = validate_password(new_password, self.disallowed_passwords)
        if errors:
            return PasswordChangeResult(
                code=PasswordChangeResultCode.VALIDATION_FAILED,
                errors=errors,
            )

        new_password_md5 = hashlib.md5(new_password.encode()).hexdigest().encode()
        new_password_bcrypt = bcrypt.hashpw(new_password_md5, bcrypt.gensalt())

        # the previous hash's cache entry must be evicted below; the
        # successful authentication above guarantees one exists
        old_password_hash = await self.users.fetch_password_hash(id=user.id)
        assert old_password_hash is not None

        await self.users.partial_update(id=user.id, pw_bcrypt=new_password_bcrypt)

        # keep the bcrypt verification cache consistent with the change
        self.password_cache.pop(old_password_hash.encode(), None)
        self.password_cache[new_password_bcrypt] = new_password_md5

        return PasswordChangeResult(code=PasswordChangeResultCode.OK)
