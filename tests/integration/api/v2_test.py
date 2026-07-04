from __future__ import annotations

import secrets
from pathlib import Path

import httpx
import respx
from fastapi import status
from httpx import AsyncClient

import app.state.services
from tests import factories

API_HEADERS = {"Host": "api.cmyui.xyz"}


async def test_v2_player_routes_return_seeded_player_and_stats(
    http_client: AsyncClient,
) -> None:
    preferred_mode = secrets.randbelow(1_000_000) + 10_000
    user = await factories.create_user(preferred_mode=preferred_mode)
    stat = await factories.create_player_stats(player_id=user.id, pp=456, plays=9)

    player_response = await http_client.get(
        f"/v2/players/{user.id}",
        headers=API_HEADERS,
    )
    assert player_response.status_code == status.HTTP_200_OK
    assert player_response.json()["data"]["id"] == user.id

    players_response = await http_client.get(
        "/v2/players",
        headers=API_HEADERS,
        params={"preferred_mode": preferred_mode, "page_size": 100},
    )
    assert players_response.status_code == status.HTTP_200_OK
    players_body = players_response.json()
    assert players_body["meta"]["total"] == 1
    assert players_body["data"][0]["id"] == user.id

    stats_response = await http_client.get(
        f"/v2/players/{user.id}/stats/{stat.mode}",
        headers=API_HEADERS,
    )
    assert stats_response.status_code == status.HTTP_200_OK
    stats_body = stats_response.json()
    assert stats_body["data"]["pp"] == 456
    assert stats_body["data"]["plays"] == 9

    all_stats_response = await http_client.get(
        f"/v2/players/{user.id}/stats",
        headers=API_HEADERS,
    )
    assert all_stats_response.status_code == status.HTTP_200_OK
    assert all_stats_response.json()["meta"]["total"] == 8

    offline_status_response = await http_client.get(
        f"/v2/players/{user.id}/status",
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
        f"/v2/maps/{beatmap.id}",
        headers=API_HEADERS,
    )
    assert map_response.status_code == status.HTTP_200_OK
    map_body = map_response.json()
    assert map_body["data"]["id"] == beatmap.id
    assert map_body["data"]["md5"] == beatmap.md5

    maps_response = await http_client.get(
        "/v2/maps",
        headers=API_HEADERS,
        params={"set_id": set_id},
    )
    assert maps_response.status_code == status.HTTP_200_OK
    maps_body = maps_response.json()
    assert maps_body["meta"]["total"] == 1
    assert maps_body["data"][0]["id"] == beatmap.id


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
        player_id=user.id,
        map_md5=beatmap.md5,
    )

    score_response = await http_client.get(
        f"/v2/scores/{score.id}",
        headers=API_HEADERS,
    )
    assert score_response.status_code == status.HTTP_200_OK
    score_body = score_response.json()
    assert score_body["data"]["id"] == score.id
    assert score_body["data"]["userid"] == user.id
    assert score_body["data"]["map_md5"] == beatmap.md5

    scores_response = await http_client.get(
        "/v2/scores",
        headers=API_HEADERS,
        params={"user_id": user.id, "map_md5": beatmap.md5},
    )
    assert scores_response.status_code == status.HTTP_200_OK
    scores_body = scores_response.json()
    assert scores_body["meta"]["total"] == 1
    assert scores_body["data"][0]["id"] == score.id


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
    clan = await factories.create_clan(owner_id=owner.id)

    clan_response = await http_client.get(
        f"/v2/clans/{clan.id}",
        headers=API_HEADERS,
    )
    assert clan_response.status_code == status.HTTP_200_OK
    clan_body = clan_response.json()
    assert clan_body["data"]["id"] == clan.id
    assert clan_body["data"]["owner"] == owner.id

    clans_response = await http_client.get("/v2/clans", headers=API_HEADERS)
    assert clans_response.status_code == status.HTTP_200_OK
    clan_ids = {clan_data["id"] for clan_data in clans_response.json()["data"]}
    assert clan.id in clan_ids


async def test_v2_clan_route_returns_not_found_for_missing_clan(
    http_client: AsyncClient,
) -> None:
    response = await http_client.get("/v2/clans/999999999", headers=API_HEADERS)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {
        "status": "error",
        "error": "Clan not found.",
    }


async def test_v2_leaderboard_route_returns_ranked_players(
    http_client: AsyncClient,
) -> None:
    user = await factories.create_user()
    await factories.create_player_stats(player_id=user.id, pp=727, plays=10)

    response = await http_client.get(
        "/v2/leaderboards/0",
        headers=API_HEADERS,
        params={"sort": "pp", "page_size": 100},
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()

    entries = [rec for rec in body["data"] if rec["player_id"] == user.id]
    assert len(entries) == 1
    assert entries[0]["name"] == user.name
    assert entries[0]["pp"] == 727
    assert entries[0]["rank"] >= 1


async def test_v2_leaderboard_route_rejects_invalid_gamemodes(
    http_client: AsyncClient,
) -> None:
    # 7 (relax mania) and 9-11 (non-std autopilot) are not playable
    # gamemodes, and are all rejected by request validation.
    for invalid_mode in (7, 9, 11):
        response = await http_client.get(
            f"/v2/leaderboards/{invalid_mode}",
            headers=API_HEADERS,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "invalid gamemode" in str(response.json()["detail"])


async def test_v2_player_stats_include_leaderboard_ranks(
    http_client: AsyncClient,
) -> None:
    user = await factories.create_user()
    await factories.create_player_stats(player_id=user.id, pp=555)
    await app.state.services.redis.zadd(
        "bancho:leaderboard:0",
        {str(user.id): 555},
    )
    await app.state.services.redis.zadd(
        f"bancho:leaderboard:0:{user.country}",
        {str(user.id): 555},
    )

    response = await http_client.get(
        f"/v2/players/{user.id}/stats/0",
        headers=API_HEADERS,
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["data"]["rank"] >= 1
    assert body["data"]["country_rank"] >= 1


async def test_v2_player_search_returns_matching_public_players(
    http_client: AsyncClient,
) -> None:
    # players must be unrestricted & verified to appear in search results.
    user = await factories.create_user(priv=3)

    response = await http_client.get(
        "/v2/players/search",
        headers=API_HEADERS,
        params={"q": user.name},
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["meta"]["total"] == 1
    assert body["data"][0] == {"id": user.id, "name": user.name}


async def test_v2_player_scores_routes_return_seeded_scores(
    http_client: AsyncClient,
) -> None:
    user = await factories.create_user()
    beatmap = await factories.create_map()
    score = await factories.create_score(player_id=user.id, map_md5=beatmap.md5)

    best_response = await http_client.get(
        f"/v2/players/{user.id}/scores",
        headers=API_HEADERS,
        params={"scope": "best", "mode": 0},
    )
    assert best_response.status_code == status.HTTP_200_OK
    best_body = best_response.json()
    assert best_body["meta"]["total"] == 1
    assert best_body["data"][0]["id"] == score.id
    assert best_body["data"][0]["beatmap"]["id"] == beatmap.id

    recent_response = await http_client.get(
        f"/v2/players/{user.id}/scores",
        headers=API_HEADERS,
        params={"scope": "recent", "mode": 0},
    )
    assert recent_response.status_code == status.HTTP_200_OK
    recent_body = recent_response.json()
    assert recent_body["meta"]["total"] == 1
    assert recent_body["data"][0]["id"] == score.id

    most_played_response = await http_client.get(
        f"/v2/players/{user.id}/most_played",
        headers=API_HEADERS,
        params={"mode": 0},
    )
    assert most_played_response.status_code == status.HTTP_200_OK
    most_played_body = most_played_response.json()
    assert most_played_body["meta"]["total"] == 1
    assert most_played_body["data"][0]["id"] == beatmap.id
    assert most_played_body["data"][0]["plays"] == 1


async def test_v2_player_scores_route_returns_not_found_for_missing_player(
    http_client: AsyncClient,
) -> None:
    response = await http_client.get(
        "/v2/players/999999999/scores",
        headers=API_HEADERS,
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {
        "status": "error",
        "error": "Player not found.",
    }


async def test_v2_map_scores_route_returns_seeded_scores(
    http_client: AsyncClient,
) -> None:
    user = await factories.create_user()
    beatmap = await factories.create_map()
    score = await factories.create_score(player_id=user.id, map_md5=beatmap.md5)

    response = await http_client.get(
        f"/v2/maps/{beatmap.id}/scores",
        headers=API_HEADERS,
        params={"mode": 0},
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["id"] == score.id
    assert body["data"][0]["score"] == score.score
    assert body["data"][0]["player"]["id"] == user.id
    assert body["data"][0]["player"]["name"] == user.name


async def test_v2_map_scores_route_returns_not_found_for_missing_map(
    http_client: AsyncClient,
) -> None:
    response = await http_client.get(
        "/v2/maps/999999999/scores",
        headers=API_HEADERS,
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {
        "status": "error",
        "error": "Map not found.",
    }


async def test_v2_server_stats_reports_player_counts(
    http_client: AsyncClient,
) -> None:
    await factories.create_user()

    response = await http_client.get("/v2/server/stats", headers=API_HEADERS)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["data"]["total_players"] >= 1
    assert body["data"]["online_players"] >= 0


REGISTRATION_HEADERS = {
    **API_HEADERS,
    "X-Forwarded-For": "127.0.0.1",
    "X-Real-IP": "127.0.0.1",
}


def _mock_out_geolocation(respx_mock: respx.MockRouter) -> None:
    respx_mock.get("http://ip-api.com/line/").mock(
        return_value=httpx.Response(
            status_code=status.HTTP_200_OK,
            content=b"\n".join((b"success", b"CA", b"43.6485", b"-79.4054")),
        ),
    )


async def _register_account(
    http_client: AsyncClient,
    *,
    username: str,
    password: str,
) -> int:
    response = await http_client.post(
        "/v2/accounts",
        headers=REGISTRATION_HEADERS,
        json={
            "username": username,
            "email": f"{username}@akatsuki.pw",
            "password": password,
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    return int(response.json()["data"]["id"])


async def test_v2_account_registration_and_session_lifecycle(
    http_client: AsyncClient,
    respx_mock: respx.MockRouter,
) -> None:
    _mock_out_geolocation(respx_mock)

    username = f"web-{secrets.token_hex(4)}"
    email = f"{username}@akatsuki.pw"
    password = "myPassword321$"

    register_response = await http_client.post(
        "/v2/accounts",
        headers=REGISTRATION_HEADERS,
        json={"username": username, "email": email, "password": password},
    )
    assert register_response.status_code == status.HTTP_201_CREATED
    register_body = register_response.json()
    assert register_body["data"]["name"] == username
    player_id = register_body["data"]["id"]

    login_response = await http_client.post(
        "/v2/sessions",
        headers=API_HEADERS,
        json={"username": username, "password": password},
    )
    assert login_response.status_code == status.HTTP_201_CREATED
    assert login_response.json()["data"]["id"] == player_id

    # the session token is transported via an http-only cookie only;
    # it must never appear in the response body.
    assert "token" not in login_response.json()["data"]
    session_cookie = login_response.headers["set-cookie"]
    assert session_cookie.startswith("bancho_session=")
    assert "HttpOnly" in session_cookie
    assert "SameSite=lax" in session_cookie

    # the client's cookie jar now authenticates subsequent requests
    whoami_response = await http_client.get(
        "/v2/sessions/current",
        headers=API_HEADERS,
    )
    assert whoami_response.status_code == status.HTTP_200_OK
    assert whoami_response.json()["data"]["id"] == player_id

    logout_response = await http_client.delete(
        "/v2/sessions/current",
        headers=API_HEADERS,
    )
    assert logout_response.status_code == status.HTTP_200_OK

    # per-request cookies are deprecated in httpx; set it on the jar
    http_client.cookies.set("bancho_session", "expired-or-revoked")
    expired_response = await http_client.get(
        "/v2/sessions/current",
        headers=API_HEADERS,
    )
    assert expired_response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_v2_account_registration_rejects_taken_usernames(
    http_client: AsyncClient,
) -> None:
    user = await factories.create_user()

    response = await http_client.post(
        "/v2/accounts",
        headers=API_HEADERS,
        json={
            "username": user.name,
            "email": f"other-{secrets.token_hex(4)}@akatsuki.pw",
            "password": "myPassword321$",
        },
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "taken" in response.json()["error"]


async def test_v2_session_creation_rejects_invalid_credentials(
    http_client: AsyncClient,
    respx_mock: respx.MockRouter,
) -> None:
    _mock_out_geolocation(respx_mock)
    username = f"web-{secrets.token_hex(4)}"
    await _register_account(
        http_client,
        username=username,
        password="myPassword321$",
    )

    response = await http_client.post(
        "/v2/sessions",
        headers=API_HEADERS,
        json={"username": username, "password": "not-the-password"},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {
        "status": "error",
        "error": "Incorrect username or password.",
    }


_PNG_AVATAR = b"\x89PNG\r\n\x1a\n" + b"avatar bytes" + b"\x49END\xae\x42\x60\x82"


async def test_v2_player_avatar_upload_lifecycle(
    http_client: AsyncClient,
    respx_mock: respx.MockRouter,
) -> None:
    _mock_out_geolocation(respx_mock)
    username = f"web-{secrets.token_hex(4)}"
    password = "myPassword321$"
    player_id = await _register_account(
        http_client,
        username=username,
        password=password,
    )

    # uploading requires authentication
    response = await http_client.put(
        f"/v2/players/{player_id}/avatar",
        headers=API_HEADERS,
        files={"avatar_file": ("avatar.png", _PNG_AVATAR, "image/png")},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    login_response = await http_client.post(
        "/v2/sessions",
        headers=API_HEADERS,
        json={"username": username, "password": password},
    )
    assert login_response.status_code == status.HTTP_201_CREATED

    # players may only update their own avatar
    response = await http_client.put(
        f"/v2/players/{player_id + 1}/avatar",
        headers=API_HEADERS,
        files={"avatar_file": ("avatar.png", _PNG_AVATAR, "image/png")},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # non-image files are rejected
    response = await http_client.put(
        f"/v2/players/{player_id}/avatar",
        headers=API_HEADERS,
        files={"avatar_file": ("avatar.png", b"not an image", "image/png")},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    # a valid image is stored where the avatar server serves from
    response = await http_client.put(
        f"/v2/players/{player_id}/avatar",
        headers=API_HEADERS,
        files={"avatar_file": ("avatar.png", _PNG_AVATAR, "image/png")},
    )
    assert response.status_code == status.HTTP_200_OK

    avatar_path = Path.cwd() / ".data/avatars" / f"{player_id}.png"
    assert avatar_path.read_bytes() == _PNG_AVATAR


async def test_v2_score_detail_embeds_beatmap_and_player(
    http_client: AsyncClient,
) -> None:
    user = await factories.create_user()
    beatmap = await factories.create_map()
    score = await factories.create_score(player_id=user.id, map_md5=beatmap.md5)

    response = await http_client.get(f"/v2/scores/{score.id}", headers=API_HEADERS)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["data"]["id"] == score.id
    assert body["data"]["player"]["id"] == user.id
    assert body["data"]["player"]["name"] == user.name
    assert body["data"]["beatmap"]["md5"] == beatmap.md5


async def test_v2_score_detail_is_gone_once_its_map_version_is(
    http_client: AsyncClient,
    respx_mock: respx.MockRouter,
) -> None:
    # a map update replaces the maps row's md5, orphaning scores set on
    # the previous version; their permalinks should 404 like everywhere
    # else the score stops being displayed
    respx_mock.get(
        url__regex=r"https://(old\.ppy\.sh|osu\.direct)/api/get_beatmaps.*",
    ).mock(
        return_value=httpx.Response(status_code=status.HTTP_200_OK, json=[]),
    )
    user = await factories.create_user()
    score = await factories.create_score(
        player_id=user.id,
        map_md5=secrets.token_hex(16),
    )

    response = await http_client.get(f"/v2/scores/{score.id}", headers=API_HEADERS)

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_v2_player_friends_lifecycle(
    http_client: AsyncClient,
    respx_mock: respx.MockRouter,
) -> None:
    _mock_out_geolocation(respx_mock)
    username = f"web-{secrets.token_hex(4)}"
    password = "myPassword321$"
    player_id = await _register_account(
        http_client,
        username=username,
        password=password,
    )
    friend = await factories.create_user()

    # listing friends requires authentication
    response = await http_client.get(
        f"/v2/players/{player_id}/friends",
        headers=API_HEADERS,
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    login_response = await http_client.post(
        "/v2/sessions",
        headers=API_HEADERS,
        json={"username": username, "password": password},
    )
    assert login_response.status_code == status.HTTP_201_CREATED

    # players may only manage their own friends
    response = await http_client.put(
        f"/v2/players/{friend.id}/friends/{player_id}",
        headers=API_HEADERS,
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # friending yourself or a missing player is rejected
    response = await http_client.put(
        f"/v2/players/{player_id}/friends/{player_id}",
        headers=API_HEADERS,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    response = await http_client.put(
        f"/v2/players/{player_id}/friends/999999999",
        headers=API_HEADERS,
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND

    # add a friend, see them in the listing, then remove them
    response = await http_client.put(
        f"/v2/players/{player_id}/friends/{friend.id}",
        headers=API_HEADERS,
    )
    assert response.status_code == status.HTTP_200_OK

    response = await http_client.get(
        f"/v2/players/{player_id}/friends",
        headers=API_HEADERS,
    )
    assert response.status_code == status.HTTP_200_OK
    assert [rec["id"] for rec in response.json()["data"]] == [friend.id]

    response = await http_client.delete(
        f"/v2/players/{player_id}/friends/{friend.id}",
        headers=API_HEADERS,
    )
    assert response.status_code == status.HTTP_200_OK

    response = await http_client.get(
        f"/v2/players/{player_id}/friends",
        headers=API_HEADERS,
    )
    assert response.json()["data"] == []


async def test_v2_player_favourites_lifecycle(
    http_client: AsyncClient,
    respx_mock: respx.MockRouter,
) -> None:
    _mock_out_geolocation(respx_mock)
    username = f"web-{secrets.token_hex(4)}"
    password = "myPassword321$"
    player_id = await _register_account(
        http_client,
        username=username,
        password=password,
    )
    beatmap = await factories.create_map()

    # mutations require authentication
    response = await http_client.put(
        f"/v2/players/{player_id}/favourites/{beatmap.set_id}",
        headers=API_HEADERS,
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    login_response = await http_client.post(
        "/v2/sessions",
        headers=API_HEADERS,
        json={"username": username, "password": password},
    )
    assert login_response.status_code == status.HTTP_201_CREATED

    response = await http_client.put(
        f"/v2/players/{player_id}/favourites/{beatmap.set_id}",
        headers=API_HEADERS,
    )
    assert response.status_code == status.HTTP_200_OK

    # favouriting twice is a no-op, not an error
    response = await http_client.put(
        f"/v2/players/{player_id}/favourites/{beatmap.set_id}",
        headers=API_HEADERS,
    )
    assert response.status_code == status.HTTP_200_OK

    # the listing is public
    anonymous_response = await http_client.get(
        f"/v2/players/{player_id}/favourites",
        headers=API_HEADERS,
    )
    assert anonymous_response.status_code == status.HTTP_200_OK
    assert anonymous_response.json()["data"] == [beatmap.set_id]

    response = await http_client.delete(
        f"/v2/players/{player_id}/favourites/{beatmap.set_id}",
        headers=API_HEADERS,
    )
    assert response.status_code == status.HTTP_200_OK

    response = await http_client.get(
        f"/v2/players/{player_id}/favourites",
        headers=API_HEADERS,
    )
    assert response.json()["data"] == []


async def test_v2_map_rating_reports_average_and_count(
    http_client: AsyncClient,
) -> None:
    beatmap = await factories.create_map()

    # no ratings yet
    response = await http_client.get(
        f"/v2/maps/{beatmap.id}/rating",
        headers=API_HEADERS,
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["data"] == {"average": None, "count": 0}

    rater_1 = await factories.create_user()
    rater_2 = await factories.create_user()
    await factories.create_rating(user_id=rater_1.id, map_md5=beatmap.md5, rating=10)
    await factories.create_rating(user_id=rater_2.id, map_md5=beatmap.md5, rating=7)

    response = await http_client.get(
        f"/v2/maps/{beatmap.id}/rating",
        headers=API_HEADERS,
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["data"]["average"] == 8.5
    assert body["data"]["count"] == 2

    response = await http_client.get("/v2/maps/999999999/rating", headers=API_HEADERS)
    assert response.status_code == status.HTTP_404_NOT_FOUND
