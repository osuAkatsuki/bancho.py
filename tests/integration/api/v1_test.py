from __future__ import annotations

import secrets

from fastapi import status
from httpx import AsyncClient

import app.state.services
from app.constants.privileges import Privileges
from app.repositories.users import UsersRepository
from tests import factories

API_HEADERS = {"Host": "api.cmyui.xyz"}


async def test_v1_search_players_returns_verified_unrestricted_matches(
    http_client: AsyncClient,
) -> None:
    suffix = secrets.token_hex(4)
    users = UsersRepository(app.state.services.database)
    visible = await factories.create_user()
    restricted = await factories.create_user()
    await users.partial_update(
        id=visible.id,
        name=f"search-{suffix}-visible",
        priv=(Privileges.UNRESTRICTED | Privileges.VERIFIED).value,
    )
    await users.partial_update(
        id=restricted.id,
        name=f"search-{suffix}-restricted",
        priv=Privileges.VERIFIED.value,
    )

    response = await http_client.get(
        "/v1/search_players",
        headers=API_HEADERS,
        params={"q": f"search-{suffix}"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "status": "success",
        "results": 1,
        "result": [
            {
                "id": visible.id,
                "name": f"search-{suffix}-visible",
            },
        ],
    }


async def test_v1_global_leaderboard_filters_restricted_players(
    http_client: AsyncClient,
) -> None:
    users = UsersRepository(app.state.services.database)
    first = await factories.create_user(country="zz")
    second = await factories.create_user(country="zz")
    restricted = await factories.create_user(country="zz")
    await users.partial_update(id=restricted.id, priv=0)
    await factories.create_player_stats(player_id=first.id, mode=0, pp=400)
    await factories.create_player_stats(player_id=second.id, mode=0, pp=300)
    await factories.create_player_stats(player_id=restricted.id, mode=0, pp=500)

    response = await http_client.get(
        "/v1/get_leaderboard",
        headers=API_HEADERS,
        params={"sort": "pp", "mode": 0, "limit": 10, "country": "zz"},
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["status"] == "success"
    assert [row["player_id"] for row in body["leaderboard"]] == [
        first.id,
        second.id,
    ]
