from __future__ import annotations

import secrets

from fastapi import status
from httpx import AsyncClient

from tests import factories

API_HEADERS = {"Host": "api.cmyui.xyz"}


async def test_v2_player_routes_return_seeded_player_and_stats(
    http_client: AsyncClient,
) -> None:
    preferred_mode = secrets.randbelow(1_000_000) + 10_000
    user = await factories.create_user(preferred_mode=preferred_mode)
    stat = await factories.create_player_stats(player_id=user["id"], pp=456, plays=9)

    player_response = await http_client.get(
        f"/v2/players/{user['id']}",
        headers=API_HEADERS,
    )
    assert player_response.status_code == status.HTTP_200_OK
    assert player_response.json()["data"]["id"] == user["id"]

    players_response = await http_client.get(
        "/v2/players",
        headers=API_HEADERS,
        params={"preferred_mode": preferred_mode, "page_size": 100},
    )
    assert players_response.status_code == status.HTTP_200_OK
    players_body = players_response.json()
    assert players_body["meta"]["total"] == 1
    assert players_body["data"][0]["id"] == user["id"]

    stats_response = await http_client.get(
        f"/v2/players/{user['id']}/stats/{stat['mode']}",
        headers=API_HEADERS,
    )
    assert stats_response.status_code == status.HTTP_200_OK
    stats_body = stats_response.json()
    assert stats_body["data"]["pp"] == 456
    assert stats_body["data"]["plays"] == 9

    all_stats_response = await http_client.get(
        f"/v2/players/{user['id']}/stats",
        headers=API_HEADERS,
    )
    assert all_stats_response.status_code == status.HTTP_200_OK
    assert all_stats_response.json()["meta"]["total"] == 8

    offline_status_response = await http_client.get(
        f"/v2/players/{user['id']}/status",
        headers=API_HEADERS,
    )
    assert offline_status_response.status_code == status.HTTP_404_NOT_FOUND
    assert offline_status_response.json() == {
        "status": "error",
        "error": "Player status not found.",
    }


async def test_v2_player_route_returns_not_found_for_missing_player(
    http_client: AsyncClient,
) -> None:
    response = await http_client.get("/v2/players/999999999", headers=API_HEADERS)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {
        "status": "error",
        "error": "Player not found.",
    }


async def test_v2_map_routes_return_seeded_map(
    http_client: AsyncClient,
) -> None:
    set_id = secrets.randbelow(1_000_000) + 20_000
    beatmap = await factories.create_map(set_id=set_id)

    map_response = await http_client.get(
        f"/v2/maps/{beatmap['id']}",
        headers=API_HEADERS,
    )
    assert map_response.status_code == status.HTTP_200_OK
    map_body = map_response.json()
    assert map_body["data"]["id"] == beatmap["id"]
    assert map_body["data"]["md5"] == beatmap["md5"]

    maps_response = await http_client.get(
        "/v2/maps",
        headers=API_HEADERS,
        params={"set_id": set_id},
    )
    assert maps_response.status_code == status.HTTP_200_OK
    maps_body = maps_response.json()
    assert maps_body["meta"]["total"] == 1
    assert maps_body["data"][0]["id"] == beatmap["id"]


async def test_v2_map_route_returns_not_found_for_missing_map(
    http_client: AsyncClient,
) -> None:
    response = await http_client.get("/v2/maps/999999999", headers=API_HEADERS)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {
        "status": "error",
        "error": "Map not found.",
    }


async def test_v2_score_routes_return_seeded_score(
    http_client: AsyncClient,
) -> None:
    user = await factories.create_user()
    beatmap = await factories.create_map()
    score = await factories.create_score(
        player_id=user["id"],
        map_md5=beatmap["md5"],
    )

    score_response = await http_client.get(
        f"/v2/scores/{score['id']}",
        headers=API_HEADERS,
    )
    assert score_response.status_code == status.HTTP_200_OK
    score_body = score_response.json()
    assert score_body["data"]["id"] == score["id"]
    assert score_body["data"]["userid"] == user["id"]
    assert score_body["data"]["map_md5"] == beatmap["md5"]

    scores_response = await http_client.get(
        "/v2/scores",
        headers=API_HEADERS,
        params={"user_id": user["id"], "map_md5": beatmap["md5"]},
    )
    assert scores_response.status_code == status.HTTP_200_OK
    scores_body = scores_response.json()
    assert scores_body["meta"]["total"] == 1
    assert scores_body["data"][0]["id"] == score["id"]


async def test_v2_score_route_returns_not_found_for_missing_score(
    http_client: AsyncClient,
) -> None:
    response = await http_client.get("/v2/scores/999999999", headers=API_HEADERS)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {
        "status": "error",
        "error": "Score not found.",
    }


async def test_v2_clan_routes_return_seeded_clan(
    http_client: AsyncClient,
) -> None:
    owner = await factories.create_user()
    clan = await factories.create_clan(owner_id=owner["id"])

    clan_response = await http_client.get(
        f"/v2/clans/{clan['id']}",
        headers=API_HEADERS,
    )
    assert clan_response.status_code == status.HTTP_200_OK
    clan_body = clan_response.json()
    assert clan_body["data"]["id"] == clan["id"]
    assert clan_body["data"]["owner"] == owner["id"]

    clans_response = await http_client.get("/v2/clans", headers=API_HEADERS)
    assert clans_response.status_code == status.HTTP_200_OK
    clan_ids = {clan_data["id"] for clan_data in clans_response.json()["data"]}
    assert clan["id"] in clan_ids


async def test_v2_clan_route_returns_not_found_for_missing_clan(
    http_client: AsyncClient,
) -> None:
    response = await http_client.get("/v2/clans/999999999", headers=API_HEADERS)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {
        "status": "error",
        "error": "Clan not found.",
    }
