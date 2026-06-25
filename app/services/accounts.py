from __future__ import annotations

import hashlib
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

import bcrypt

from app._typing import IPAddress
from app.adapters.database import Database
from app.constants import regexes
from app.logging import Ansi
from app.logging import log
from app.repositories.stats import StatsRepository
from app.repositories.users import User
from app.repositories.users import UsersRepository
from app.state.services import Geolocation


class IPResolver(Protocol):
    def get_ip(self, headers: Mapping[str, str]) -> IPAddress: ...


class RegistrationErrors(dict[str, list[str]]):
    pass


@dataclass(frozen=True)
class RegisteredAccount:
    player: User
    password_md5: bytes
    password_bcrypt: bytes


class AccountRegistrationResultCode(StrEnum):
    OK = "ok"
    MISSING_REQUIRED_PARAMS = "missing_required_params"
    INGAME_REGISTRATION_DISABLED = "ingame_registration_disabled"
    VALIDATION_FAILED = "validation_failed"


@dataclass(frozen=True)
class AccountRegistrationResult:
    code: AccountRegistrationResultCode
    errors: RegistrationErrors | None = None


@dataclass(frozen=True)
class AccountRegistrationService:
    users: UsersRepository
    stats: StatsRepository
    database: Database
    password_cache: dict[bytes, bytes]
    ip_resolver: IPResolver
    fetch_geoloc: Callable[
        [IPAddress, Mapping[str, str] | None],
        Awaitable[Geolocation | None],
    ]
    increment_metric: Callable[[str], None]
    ingame_registration_disallowed: bool
    disallowed_names: Sequence[str]
    disallowed_passwords: Sequence[str]

    async def check_or_register(
        self,
        *,
        username: str,
        email: str,
        password: str,
        should_create_account: bool,
        request_headers: Mapping[str, str],
    ) -> AccountRegistrationResult:
        if not all((username, email, password)):
            return AccountRegistrationResult(
                code=AccountRegistrationResultCode.MISSING_REQUIRED_PARAMS,
            )

        # Disable in-game registration if enabled
        if self.ingame_registration_disallowed:
            return AccountRegistrationResult(
                code=AccountRegistrationResultCode.INGAME_REGISTRATION_DISABLED,
            )

        errors = await self.validate_registration(
            username=username,
            email=email,
            password=password,
        )
        if errors:
            return AccountRegistrationResult(
                code=AccountRegistrationResultCode.VALIDATION_FAILED,
                errors=errors,
            )

        if should_create_account:
            # the client isn't just checking values,
            # they want to register the account now.
            registered_account = await self.create_account(
                username=username,
                email=email,
                password=password,
                request_headers=request_headers,
            )
            player = registered_account.player

            self.increment_metric("bancho.registrations")
            log(f"<{username} ({player.id})> has registered!", Ansi.LGREEN)

        return AccountRegistrationResult(code=AccountRegistrationResultCode.OK)

    async def validate_registration(
        self,
        *,
        username: str,
        email: str,
        password: str,
    ) -> RegistrationErrors:
        errors: RegistrationErrors = RegistrationErrors()

        # Usernames must:
        # - be within 2-15 characters in length
        # - not contain both ' ' and '_', one is fine
        # - not be in the config's `disallowed_names` list
        # - not already be taken by another player
        if not regexes.USERNAME.match(username):
            errors.setdefault("username", []).append(
                "Must be 2-15 characters in length.",
            )

        if "_" in username and " " in username:
            errors.setdefault("username", []).append(
                'May contain "_" and " ", but not both.',
            )

        if username in self.disallowed_names:
            errors.setdefault("username", []).append(
                "Disallowed username; pick another.",
            )

        if "username" not in errors:
            if await self.users.fetch_one(name=username):
                errors.setdefault("username", []).append(
                    "Username already taken by another player.",
                )

        # Emails must:
        # - match the regex `^[^@\s]{1,200}@[^@\s\.]{1,30}\.[^@\.\s]{1,24}$`
        # - not already be taken by another player
        if not regexes.EMAIL.match(email):
            errors.setdefault("user_email", []).append("Invalid email syntax.")
        else:
            if await self.users.fetch_one(email=email):
                errors.setdefault("user_email", []).append(
                    "Email already taken by another player.",
                )

        # Passwords must:
        # - be within 8-32 characters in length
        # - have more than 3 unique characters
        # - not be in the config's `disallowed_passwords` list
        if not 8 <= len(password) <= 32:
            errors.setdefault("password", []).append(
                "Must be 8-32 characters in length.",
            )

        if len(set(password)) <= 3:
            errors.setdefault("password", []).append(
                "Must have more than 3 unique characters.",
            )

        if password.lower() in self.disallowed_passwords:
            errors.setdefault("password", []).append(
                "That password was deemed too simple.",
            )

        return errors

    async def create_account(
        self,
        *,
        username: str,
        email: str,
        password: str,
        request_headers: Mapping[str, str],
    ) -> RegisteredAccount:
        password_md5 = hashlib.md5(password.encode()).hexdigest().encode()
        password_bcrypt = bcrypt.hashpw(password_md5, bcrypt.gensalt())
        self.password_cache[password_bcrypt] = password_md5

        ip = self.ip_resolver.get_ip(request_headers)
        geoloc = await self.fetch_geoloc(ip, request_headers)
        country = geoloc["country"]["acronym"] if geoloc is not None else "XX"

        async with self.database.transaction():
            player = await self.users.create(
                name=username,
                email=email,
                pw_bcrypt=password_bcrypt,
                country=country,
            )
            await self.stats.create_all_modes(player_id=player.id)

        return RegisteredAccount(
            player=player,
            password_md5=password_md5,
            password_bcrypt=password_bcrypt,
        )
