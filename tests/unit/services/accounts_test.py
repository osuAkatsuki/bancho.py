from __future__ import annotations

import app.services.accounts as accounts


class _FakeUsers:
    def __init__(
        self,
        *,
        existing_name: str | None = None,
        existing_email: str | None = None,
    ) -> None:
        self.existing_name = existing_name
        self.existing_email = existing_email

    async def fetch_one(
        self,
        *,
        name: str | None = None,
        email: str | None = None,
    ) -> object | None:
        if name == self.existing_name or email == self.existing_email:
            return object()

        return None


async def _fetch_geoloc(
    ip: object,
    headers: object | None,
) -> None:
    return None


def _service(*, users: object | None = None) -> accounts.AccountRegistrationService:
    return accounts.AccountRegistrationService(
        users=users or _FakeUsers(),
        stats=object(),
        database=object(),
        password_cache={},
        ip_resolver=object(),
        fetch_geoloc=_fetch_geoloc,
        increment_metric=lambda metric: None,
        ingame_registration_disallowed=False,
        disallowed_names=["blocked"],
        disallowed_passwords=["password123"],
    )


async def test_account_registration_validation_reports_invalid_user_input() -> None:
    errors = await _service().validate_registration(
        username="bad_name with",
        email="not-email",
        password="aaaabbbb",
    )

    assert errors == {
        "username": ['May contain "_" and " ", but not both.'],
        "user_email": ["Invalid email syntax."],
        "password": ["Must have more than 3 unique characters."],
    }


async def test_account_registration_validation_reports_existing_fields() -> None:
    errors = await _service(
        users=_FakeUsers(
            existing_name="cmyui",
            existing_email="cmyui@example.com",
        ),
    ).validate_registration(
        username="cmyui",
        email="cmyui@example.com",
        password="correcthorsebattery",
    )

    assert errors == {
        "username": ["Username already taken by another player."],
        "user_email": ["Email already taken by another player."],
    }
