from __future__ import annotations

from app.repositories import scores as scores_repo
from app.repositories import users as users_repo
from tests import factories


async def test_fetch_beatmap_leaderboard_scores_orders_scores_and_filters_restricted_users() -> (
    None
):
    beatmap = await factories.create_map()
    requester = await factories.create_user()
    unrestricted_user = await factories.create_user()
    restricted_user = await factories.create_user()
    await users_repo.partial_update(
        id=requester["id"],
        priv=0,
    )
    await users_repo.partial_update(
        id=restricted_user["id"],
        priv=0,
    )

    requester_score = await factories.create_score(
        player_id=requester["id"],
        map_md5=beatmap["md5"],
        score=900_000,
        mods=0,
    )
    unrestricted_score = await factories.create_score(
        player_id=unrestricted_user["id"],
        map_md5=beatmap["md5"],
        score=500_000,
        mods=0,
    )
    await factories.create_score(
        player_id=restricted_user["id"],
        map_md5=beatmap["md5"],
        score=1_000_000,
        mods=0,
    )

    score_rows = await scores_repo.fetch_beatmap_leaderboard_scores(
        map_md5=beatmap["md5"],
        mode=0,
        user_id=requester["id"],
        scoring_metric="score",
    )

    assert [row["id"] for row in score_rows] == [
        requester_score["id"],
        unrestricted_score["id"],
    ]
    assert [row["leaderboard_value"] for row in score_rows] == [900_000, 500_000]


async def test_fetch_personal_best_leaderboard_rank_ignores_restricted_scores() -> None:
    beatmap = await factories.create_map()
    player = await factories.create_user()
    higher_unrestricted_user = await factories.create_user()
    higher_restricted_user = await factories.create_user()
    await users_repo.partial_update(
        id=higher_restricted_user["id"],
        priv=0,
    )

    player_score = await factories.create_score(
        player_id=player["id"],
        map_md5=beatmap["md5"],
        score=700_000,
        mods=0,
    )
    await factories.create_score(
        player_id=higher_unrestricted_user["id"],
        map_md5=beatmap["md5"],
        score=800_000,
        mods=0,
    )
    await factories.create_score(
        player_id=higher_restricted_user["id"],
        map_md5=beatmap["md5"],
        score=900_000,
        mods=0,
    )

    personal_best = await scores_repo.fetch_personal_best_leaderboard_score(
        map_md5=beatmap["md5"],
        mode=0,
        user_id=player["id"],
        scoring_metric="score",
    )
    rank = await scores_repo.fetch_personal_best_leaderboard_rank(
        map_md5=beatmap["md5"],
        mode=0,
        scoring_metric="score",
        score=700_000,
    )

    assert personal_best is not None
    assert personal_best["id"] == player_score["id"]
    assert rank == 2


async def test_fetch_beatmap_leaderboard_scores_applies_mods_friends_and_country_filters() -> (
    None
):
    beatmap = await factories.create_map()
    requester = await factories.create_user(country="ca")
    friend = await factories.create_user(country="us")
    same_country_user = await factories.create_user(country="ca")
    other_user = await factories.create_user(country="jp")

    requester_score = await factories.create_score(
        player_id=requester["id"],
        map_md5=beatmap["md5"],
        score=900_000,
        mods=64,
    )
    friend_score = await factories.create_score(
        player_id=friend["id"],
        map_md5=beatmap["md5"],
        score=800_000,
        mods=0,
    )
    same_country_score = await factories.create_score(
        player_id=same_country_user["id"],
        map_md5=beatmap["md5"],
        score=700_000,
        mods=0,
    )
    await factories.create_score(
        player_id=other_user["id"],
        map_md5=beatmap["md5"],
        score=600_000,
        mods=0,
    )

    mods_rows = await scores_repo.fetch_beatmap_leaderboard_scores(
        map_md5=beatmap["md5"],
        mode=0,
        user_id=requester["id"],
        scoring_metric="score",
        mods=64,
    )
    friend_rows = await scores_repo.fetch_beatmap_leaderboard_scores(
        map_md5=beatmap["md5"],
        mode=0,
        user_id=requester["id"],
        scoring_metric="score",
        friend_ids={requester["id"], friend["id"]},
    )
    country_rows = await scores_repo.fetch_beatmap_leaderboard_scores(
        map_md5=beatmap["md5"],
        mode=0,
        user_id=requester["id"],
        scoring_metric="score",
        country="ca",
    )

    assert [row["id"] for row in mods_rows] == [requester_score["id"]]
    assert [row["id"] for row in friend_rows] == [
        requester_score["id"],
        friend_score["id"],
    ]
    assert [row["id"] for row in country_rows] == [
        requester_score["id"],
        same_country_score["id"],
    ]
