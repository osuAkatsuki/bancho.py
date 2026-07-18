from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import status
from httpx import AsyncClient

from app.application import Application
from app.constants.privileges import Privileges
from tests.factories import TestDataFactory

API_HEADERS = {"Host": "api.cmyui.xyz"}


async def test_v1_search_players_returns_verified_unrestricted_matches(
    application: Application,
    test_data: TestDataFactory,
    http_client: AsyncClient,
) -> None:
    suffix = secrets.token_hex(4)
    users = application.repositories.users
    visible = await test_data.create_user()
    restricted = await test_data.create_user()
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
    application: Application,
    test_data: TestDataFactory,
    http_client: AsyncClient,
) -> None:
    users = application.repositories.users
    first = await test_data.create_user(country="zz")
    second = await test_data.create_user(country="zz")
    restricted = await test_data.create_user(country="zz")
    await users.partial_update(id=restricted.id, priv=0)
    await test_data.create_player_stats(player_id=first.id, mode=0, pp=400)
    await test_data.create_player_stats(player_id=second.id, mode=0, pp=300)
    await test_data.create_player_stats(player_id=restricted.id, mode=0, pp=500)

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


async def test_v1_hidden_player_resources_are_not_exposed(
    test_data: TestDataFactory,
    http_client: AsyncClient,
) -> None:
    # a hidden (unverified) player with a score & a replay on disk
    hidden = await test_data.create_user(priv=int(Privileges.UNRESTRICTED))
    beatmap = await test_data.create_map()
    score = await test_data.create_score(player_id=hidden.id, map_md5=beatmap.md5)
    replay_path = Path.cwd() / ".data/osr" / f"{score.id}.osr"
    replay_path.write_bytes(b"raw replay frames")
    try:
        # the v1 api is anonymous, so all of their resources are missing
        requests = [
            ("/v1/get_player_info", {"id": hidden.id, "scope": "all"}),
            ("/v1/get_player_status", {"id": hidden.id}),
            ("/v1/get_player_scores", {"id": hidden.id, "scope": "best"}),
            ("/v1/get_player_most_played", {"id": hidden.id}),
            ("/v1/get_score_info", {"id": score.id}),
            ("/v1/get_replay", {"id": score.id}),
            ("/v1/get_replay", {"id": score.id, "include_headers": False}),
        ]
        for url, params in requests:
            response = await http_client.get(url, headers=API_HEADERS, params=params)
            assert response.status_code == status.HTTP_404_NOT_FOUND, (url, params)
    finally:
        replay_path.unlink(missing_ok=True)
