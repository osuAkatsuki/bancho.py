from __future__ import annotations

import secrets

import app.state.services
from app.repositories.stats import StatsRepository
from app.repositories.users import UsersRepository
from tests import factories


async def test_fetch_leaderboard_stats_rows_filters_country_restricted_and_zero_sort() -> (
    None
):
    country = secrets.token_hex(1)
    other_country = "aa" if country != "aa" else "bb"
    top_player = await factories.create_user(country=country)
    lower_player = await factories.create_user(country=country)
    zero_pp_player = await factories.create_user(country=country)
    restricted_player = await factories.create_user(country=country)
    other_country_player = await factories.create_user(country=other_country)
    users = UsersRepository(app.state.services.database)
    stats = StatsRepository(app.state.services.database)

    await factories.create_player_stats(player_id=top_player.id, pp=600, plays=10)
    await factories.create_player_stats(
        player_id=lower_player.id,
        pp=300,
        plays=20,
    )
    await factories.create_player_stats(
        player_id=zero_pp_player.id,
        pp=0,
        plays=30,
    )
    await factories.create_player_stats(
        player_id=restricted_player.id,
        pp=900,
        plays=40,
    )
    await factories.create_player_stats(
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
