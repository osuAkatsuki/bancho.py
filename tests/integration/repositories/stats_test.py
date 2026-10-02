from __future__ import annotations

import secrets

from app.application import Application
from tests.factories import TestDataFactory


async def test_fetch_leaderboard_stats_rows_filters_country_restricted_and_zero_sort(
    application: Application,
    test_data: TestDataFactory,
) -> None:
    country = secrets.token_hex(1)
    other_country = "aa" if country != "aa" else "bb"
    top_player = await test_data.create_user(country=country)
    lower_player = await test_data.create_user(country=country)
    zero_pp_player = await test_data.create_user(country=country)
    restricted_player = await test_data.create_user(country=country)
    other_country_player = await test_data.create_user(country=other_country)
    users = application.repositories.users
    stats = application.repositories.stats

    await test_data.create_player_stats(player_id=top_player.id, pp=600, plays=10)
    await test_data.create_player_stats(
        player_id=lower_player.id,
        pp=300,
        plays=20,
    )
    await test_data.create_player_stats(
        player_id=zero_pp_player.id,
        pp=0,
        plays=30,
    )
    await test_data.create_player_stats(
        player_id=restricted_player.id,
        pp=900,
        plays=40,
    )
    await test_data.create_player_stats(
        player_id=other_country_player.id,
        pp=800,
        plays=50,
    )
    await users.partial_update(id=restricted_player.id, priv=0)

    rows = await stats.fetch_leaderboard_stats_rows(
        sort="pp",
        mode=0,
        limit=10,
        offset=0,
        country=country,
    )

    assert [row.player_id for row in rows] == [
        top_player.id,
        lower_player.id,
    ]
    assert [row.pp for row in rows] == [600, 300]
