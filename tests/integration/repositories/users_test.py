from __future__ import annotations

import secrets

import app.state.services
from app.constants.privileges import Privileges
from app.repositories.users import UsersRepository
from tests import factories


async def test_search_public_filters_to_verified_unrestricted_users() -> None:
    users = UsersRepository(app.state.services.database)
    suffix = secrets.token_hex(4)
    visible = await factories.create_user()
    unverified = await factories.create_user()
    restricted = await factories.create_user()

    await users.partial_update(
        id=visible["id"],
        name=f"search-{suffix}-visible",
        priv=(Privileges.UNRESTRICTED | Privileges.VERIFIED).value,
    )
    await users.partial_update(
        id=unverified["id"],
        name=f"search-{suffix}-unverified",
        priv=Privileges.UNRESTRICTED.value,
    )
    await users.partial_update(
        id=restricted["id"],
        name=f"search-{suffix}-restricted",
        priv=Privileges.VERIFIED.value,
    )

    rows = await users.search_public(name=f"search-{suffix}")

    assert rows == [
        {
            "id": visible["id"],
            "name": f"search-{suffix}-visible",
        },
    ]
