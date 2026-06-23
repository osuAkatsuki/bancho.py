from __future__ import annotations

import pytest

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


async def test_fetch_beatmap_leaderboard_scores_orders_by_pp_and_formats_clan_names() -> (
    None
):
    beatmap = await factories.create_map()
    clan_player = await factories.create_user()
    other_player = await factories.create_user()
    clan = await factories.create_clan(owner_id=clan_player["id"])
    await users_repo.partial_update(
        id=clan_player["id"],
        clan_id=clan["id"],
    )

    clan_score = await factories.create_score(
        player_id=clan_player["id"],
        map_md5=beatmap["md5"],
        score=100_000,
        pp=250.5,
        mods=0,
    )
    other_score = await factories.create_score(
        player_id=other_player["id"],
        map_md5=beatmap["md5"],
        score=900_000,
        pp=100.0,
        mods=0,
    )

    score_rows = await scores_repo.fetch_beatmap_leaderboard_scores(
        map_md5=beatmap["md5"],
        mode=0,
        user_id=clan_player["id"],
        scoring_metric="pp",
    )

    assert [row["id"] for row in score_rows] == [
        clan_score["id"],
        other_score["id"],
    ]
    assert [row["leaderboard_value"] for row in score_rows] == [250.5, 100.0]
    assert [row["name"] for row in score_rows] == [
        f"[{clan['tag']}] {clan_player['name']}",
        other_player["name"],
    ]


async def test_fetch_first_place_score_uses_metric_and_ignores_restricted_users() -> (
    None
):
    beatmap = await factories.create_map()
    first_place_player = await factories.create_user()
    higher_score_player = await factories.create_user()
    restricted_higher_pp_player = await factories.create_user()
    await users_repo.partial_update(
        id=restricted_higher_pp_player["id"],
        priv=0,
    )

    await factories.create_score(
        player_id=first_place_player["id"],
        map_md5=beatmap["md5"],
        score=800_000,
        pp=300.0,
        mods=0,
    )
    await factories.create_score(
        player_id=higher_score_player["id"],
        map_md5=beatmap["md5"],
        score=900_000,
        pp=250.0,
        mods=0,
    )
    await factories.create_score(
        player_id=restricted_higher_pp_player["id"],
        map_md5=beatmap["md5"],
        score=700_000,
        pp=400.0,
        mods=0,
    )

    first_place_score = await scores_repo.fetch_first_place_score(
        map_md5=beatmap["md5"],
        mode=0,
        scoring_metric="pp",
    )

    assert first_place_score == {
        "id": first_place_player["id"],
        "name": first_place_player["name"],
    }


async def test_fetch_one_by_online_checksum_returns_matching_score() -> None:
    beatmap = await factories.create_map()
    player = await factories.create_user()
    score = await factories.create_score(
        player_id=player["id"],
        map_md5=beatmap["md5"],
    )

    fetched_score = await scores_repo.fetch_one_by_online_checksum(
        score["online_checksum"],
    )
    missing_score = await scores_repo.fetch_one_by_online_checksum("missing-checksum")

    assert fetched_score is not None
    assert fetched_score["id"] == score["id"]
    assert missing_score is None


async def test_create_rejects_duplicate_online_checksum() -> None:
    beatmap = await factories.create_map()
    player = await factories.create_user()
    online_checksum = "duplicated-online-score-checksum"

    await factories.create_score(
        player_id=player["id"],
        map_md5=beatmap["md5"],
        online_checksum=online_checksum,
    )

    with pytest.raises(scores_repo.DuplicateScoreError):
        await factories.create_score(
            player_id=player["id"],
            map_md5=beatmap["md5"],
            online_checksum=online_checksum,
        )


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


async def test_fetch_personal_best_leaderboard_score_and_rank_use_pp_metric() -> None:
    beatmap = await factories.create_map()
    player = await factories.create_user()
    higher_pp_user = await factories.create_user()
    lower_pp_user = await factories.create_user()
    restricted_higher_pp_user = await factories.create_user()
    await users_repo.partial_update(
        id=restricted_higher_pp_user["id"],
        priv=0,
    )

    await factories.create_score(
        player_id=player["id"],
        map_md5=beatmap["md5"],
        score=900_000,
        pp=100.0,
        mods=0,
    )
    player_best_pp_score = await factories.create_score(
        player_id=player["id"],
        map_md5=beatmap["md5"],
        score=800_000,
        pp=300.0,
        mods=0,
    )
    await factories.create_score(
        player_id=higher_pp_user["id"],
        map_md5=beatmap["md5"],
        score=500_000,
        pp=400.0,
        mods=0,
    )
    await factories.create_score(
        player_id=lower_pp_user["id"],
        map_md5=beatmap["md5"],
        score=1_000_000,
        pp=250.0,
        mods=0,
    )
    await factories.create_score(
        player_id=restricted_higher_pp_user["id"],
        map_md5=beatmap["md5"],
        score=600_000,
        pp=500.0,
        mods=0,
    )

    personal_best = await scores_repo.fetch_personal_best_leaderboard_score(
        map_md5=beatmap["md5"],
        mode=0,
        user_id=player["id"],
        scoring_metric="pp",
    )
    rank = await scores_repo.fetch_personal_best_leaderboard_rank(
        map_md5=beatmap["md5"],
        mode=0,
        scoring_metric="pp",
        score=300.0,
    )

    assert personal_best is not None
    assert personal_best["id"] == player_best_pp_score["id"]
    assert personal_best["leaderboard_value"] == 300.0
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
