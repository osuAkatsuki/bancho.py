from __future__ import annotations

import secrets

from app.application import Application
from app.constants.privileges import Privileges
from tests.factories import TestDataFactory


async def test_search_public_filters_to_verified_unrestricted_users(
    application: Application,
    test_data: TestDataFactory,
) -> None:
    users = application.repositories.users
    suffix = secrets.token_hex(4)
    visible = await test_data.create_user()
    unverified = await test_data.create_user()
    restricted = await test_data.create_user()

    await users.partial_update(
        id=visible.id,
        name=f"search-{suffix}-visible",
        priv=(Privileges.UNRESTRICTED | Privileges.VERIFIED).value,
    )
    await users.partial_update(
        id=unverified.id,
        name=f"search-{suffix}-unverified",
        priv=Privileges.UNRESTRICTED.value,
    )
    await users.partial_update(
        id=restricted.id,
        name=f"search-{suffix}-restricted",
        priv=Privileges.VERIFIED.value,
    )

    rows = await users.search_public(name=f"search-{suffix}")

    assert [(row.id, row.name) for row in rows] == [
        (visible.id, f"search-{suffix}-visible"),
    ]


async def test_fetch_api_keys_returns_configured_keys(
    application: Application,
    test_data: TestDataFactory,
) -> None:
    users = application.repositories.users
    user = await test_data.create_user()
    api_key = secrets.token_hex(16)
    await users.partial_update(id=user.id, api_key=api_key)

    records = await users.fetch_api_keys()

    assert (user.id, api_key) in {
        (record.user_id, record.api_key) for record in records
    }


async def test_fetch_expired_donor_ids_filters_by_expiry_and_privilege(
    application: Application,
    test_data: TestDataFactory,
) -> None:
    users = application.repositories.users
    expired_donor = await test_data.create_user()
    expired_non_donor = await test_data.create_user()
    active_donor = await test_data.create_user()

    await users.partial_update(
        id=expired_donor.id,
        donor_end=1,
        priv=expired_donor.priv | Privileges.DONATOR.value,
    )
    await users.partial_update(id=expired_non_donor.id, donor_end=1)
    await users.partial_update(
        id=active_donor.id,
        donor_end=0x7FFFFFFF,
        priv=active_donor.priv | Privileges.DONATOR.value,
    )

    expired_ids = await users.fetch_expired_donor_ids()

    assert expired_donor.id in expired_ids
    assert expired_non_donor.id not in expired_ids
    assert active_donor.id not in expired_ids
