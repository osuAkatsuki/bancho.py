from __future__ import annotations

import app.state.services
from app.constants.beatmap_statuses import RankedStatus
from app.constants.score_statuses import SubmissionStatus
from app.repositories.maps import MapsRepository
from app.repositories.scores import ScoresRepository
from app.repositories.users import UsersRepository
from tests import factories


async def test_fetch_beatmap_leaderboard_scores_orders_scores_and_filters_restricted_users() -> (
    None
):
    beatmap = await factories.create_map()
    requester = await factories.create_user()
    unrestricted_user = await factories.create_user()
    restricted_user = await factories.create_user()
    users = UsersRepository(app.state.services.database)
    scores = ScoresRepository(app.state.services.database)
    await users.partial_update(
        id=requester["id"],
        priv=0,
    )
    await users.partial_update(
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

    score_rows = await scores.fetch_beatmap_leaderboard_scores(
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
    scores = ScoresRepository(app.state.services.database)
    await UsersRepository(app.state.services.database).partial_update(
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

    score_rows = await scores.fetch_beatmap_leaderboard_scores(
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
    scores = ScoresRepository(app.state.services.database)
    await UsersRepository(app.state.services.database).partial_update(
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

    first_place_score = await scores.fetch_first_place_score(
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
    scores = ScoresRepository(app.state.services.database)

    fetched_score = await scores.fetch_one_by_online_checksum(
        score["online_checksum"],
    )
    missing_score = await scores.fetch_one_by_online_checksum(
        "missing-checksum",
    )

    assert fetched_score is not None
    assert fetched_score["id"] == score["id"]
    assert missing_score is None


async def test_fetch_personal_best_leaderboard_rank_ignores_restricted_scores() -> None:
    beatmap = await factories.create_map()
    player = await factories.create_user()
    higher_unrestricted_user = await factories.create_user()
    higher_restricted_user = await factories.create_user()
    users = UsersRepository(app.state.services.database)
    scores = ScoresRepository(app.state.services.database)
    await users.partial_update(
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

    personal_best = await scores.fetch_personal_best_leaderboard_score(
        map_md5=beatmap["md5"],
        mode=0,
        user_id=player["id"],
        scoring_metric="score",
    )
    rank = await scores.fetch_personal_best_leaderboard_rank(
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
    users = UsersRepository(app.state.services.database)
    scores = ScoresRepository(app.state.services.database)
    await users.partial_update(
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

    personal_best = await scores.fetch_personal_best_leaderboard_score(
        map_md5=beatmap["md5"],
        mode=0,
        user_id=player["id"],
        scoring_metric="pp",
    )
    rank = await scores.fetch_personal_best_leaderboard_rank(
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
    scores = ScoresRepository(app.state.services.database)

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

    mods_rows = await scores.fetch_beatmap_leaderboard_scores(
        map_md5=beatmap["md5"],
        mode=0,
        user_id=requester["id"],
        scoring_metric="score",
        mods=64,
    )
    friend_rows = await scores.fetch_beatmap_leaderboard_scores(
        map_md5=beatmap["md5"],
        mode=0,
        user_id=requester["id"],
        scoring_metric="score",
        friend_ids={requester["id"], friend["id"]},
    )
    country_rows = await scores.fetch_beatmap_leaderboard_scores(
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


async def test_fetch_public_player_best_scores_filters_best_ranked_and_loved_maps() -> (
    None
):
    ranked_map = await factories.create_map()
    loved_map = await factories.create_map()
    pending_map = await factories.create_map()
    player = await factories.create_user()
    maps = MapsRepository(app.state.services.database)
    scores = ScoresRepository(app.state.services.database)

    await maps.partial_update(
        id=loved_map["id"],
        status=RankedStatus.Loved.value,
    )
    await maps.partial_update(
        id=pending_map["id"],
        status=RankedStatus.Pending.value,
    )

    ranked_score = await factories.create_score(
        player_id=player["id"],
        map_md5=ranked_map["md5"],
        pp=300.0,
        status=SubmissionStatus.BEST.value,
    )
    loved_score = await factories.create_score(
        player_id=player["id"],
        map_md5=loved_map["md5"],
        pp=400.0,
        status=SubmissionStatus.BEST.value,
    )
    await factories.create_score(
        player_id=player["id"],
        map_md5=ranked_map["md5"],
        pp=500.0,
        status=SubmissionStatus.SUBMITTED.value,
    )
    await factories.create_score(
        player_id=player["id"],
        map_md5=pending_map["md5"],
        pp=600.0,
        status=SubmissionStatus.BEST.value,
    )

    rows_without_loved = await scores.fetch_public_player_scores(
        user_id=player["id"],
        mode=0,
        mods=None,
        strong_mods_equality=True,
        scope="best",
        limit=10,
        include_loved=False,
        include_failed=True,
    )
    rows_with_loved = await scores.fetch_public_player_scores(
        user_id=player["id"],
        mode=0,
        mods=None,
        strong_mods_equality=True,
        scope="best",
        limit=10,
        include_loved=True,
        include_failed=True,
    )

    assert [row["id"] for row in rows_without_loved] == [ranked_score["id"]]
    assert [row["id"] for row in rows_with_loved] == [
        loved_score["id"],
        ranked_score["id"],
    ]


async def test_fetch_public_player_recent_scores_filters_failed_and_mods() -> None:
    beatmap = await factories.create_map()
    player = await factories.create_user()
    scores = ScoresRepository(app.state.services.database)

    hd_score = await factories.create_score(
        player_id=player["id"],
        map_md5=beatmap["md5"],
        mods=64,
        status=SubmissionStatus.SUBMITTED.value,
    )
    hr_score = await factories.create_score(
        player_id=player["id"],
        map_md5=beatmap["md5"],
        mods=16,
        status=SubmissionStatus.SUBMITTED.value,
    )
    hdhr_score = await factories.create_score(
        player_id=player["id"],
        map_md5=beatmap["md5"],
        mods=80,
        status=SubmissionStatus.SUBMITTED.value,
    )
    failed_score = await factories.create_score(
        player_id=player["id"],
        map_md5=beatmap["md5"],
        mods=80,
        status=SubmissionStatus.FAILED.value,
    )

    rows_without_failed = await scores.fetch_public_player_scores(
        user_id=player["id"],
        mode=0,
        mods=None,
        strong_mods_equality=True,
        scope="recent",
        limit=10,
        include_loved=False,
        include_failed=False,
    )
    weak_mod_rows = await scores.fetch_public_player_scores(
        user_id=player["id"],
        mode=0,
        mods=80,
        strong_mods_equality=False,
        scope="recent",
        limit=10,
        include_loved=False,
        include_failed=True,
    )
    strong_mod_rows = await scores.fetch_public_player_scores(
        user_id=player["id"],
        mode=0,
        mods=80,
        strong_mods_equality=True,
        scope="recent",
        limit=10,
        include_loved=False,
        include_failed=True,
    )

    assert {row["id"] for row in rows_without_failed} == {
        hd_score["id"],
        hr_score["id"],
        hdhr_score["id"],
    }
    assert {row["id"] for row in weak_mod_rows} == {
        hd_score["id"],
        hr_score["id"],
        hdhr_score["id"],
        failed_score["id"],
    }
    assert {row["id"] for row in strong_mod_rows} == {
        hdhr_score["id"],
        failed_score["id"],
    }


async def test_fetch_public_player_most_played_maps_groups_by_map() -> None:
    most_played_map = await factories.create_map()
    other_map = await factories.create_map()
    player = await factories.create_user()
    scores = ScoresRepository(app.state.services.database)

    await factories.create_score(
        player_id=player["id"],
        map_md5=most_played_map["md5"],
    )
    await factories.create_score(
        player_id=player["id"],
        map_md5=most_played_map["md5"],
    )
    await factories.create_score(
        player_id=player["id"],
        map_md5=other_map["md5"],
    )

    rows = await scores.fetch_public_player_most_played_maps(
        user_id=player["id"],
        mode=0,
        limit=10,
    )

    assert [(row["md5"], row["plays"]) for row in rows] == [
        (most_played_map["md5"], 2),
        (other_map["md5"], 1),
    ]


async def test_fetch_public_map_scores_filters_restricted_and_sorts_by_mode_metric() -> (
    None
):
    beatmap = await factories.create_map()
    score_player = await factories.create_user()
    pp_player = await factories.create_user()
    restricted_player = await factories.create_user()
    users = UsersRepository(app.state.services.database)
    scores = ScoresRepository(app.state.services.database)
    await users.partial_update(id=restricted_player["id"], priv=0)

    await factories.create_score(
        player_id=score_player["id"],
        map_md5=beatmap["md5"],
        score=900_000,
        pp=100.0,
        mode=0,
        status=SubmissionStatus.BEST.value,
    )
    await factories.create_score(
        player_id=pp_player["id"],
        map_md5=beatmap["md5"],
        score=500_000,
        pp=300.0,
        mode=0,
        status=SubmissionStatus.BEST.value,
    )
    await factories.create_score(
        player_id=restricted_player["id"],
        map_md5=beatmap["md5"],
        score=1_000_000,
        pp=400.0,
        mode=0,
        status=SubmissionStatus.BEST.value,
    )
    await factories.create_score(
        player_id=score_player["id"],
        map_md5=beatmap["md5"],
        score=900_000,
        pp=100.0,
        mode=4,
        status=SubmissionStatus.BEST.value,
    )
    await factories.create_score(
        player_id=pp_player["id"],
        map_md5=beatmap["md5"],
        score=500_000,
        pp=300.0,
        mode=4,
        status=SubmissionStatus.BEST.value,
    )

    vanilla_rows = await scores.fetch_public_map_scores(
        map_md5=beatmap["md5"],
        mode=0,
        mods=None,
        strong_mods_equality=True,
        scope="best",
        limit=10,
    )
    relax_rows = await scores.fetch_public_map_scores(
        map_md5=beatmap["md5"],
        mode=4,
        mods=None,
        strong_mods_equality=True,
        scope="best",
        limit=10,
    )

    assert [row["player_name"] for row in vanilla_rows] == [
        score_player["name"],
        pp_player["name"],
    ]
    assert [row["player_name"] for row in relax_rows] == [
        pp_player["name"],
        score_player["name"],
    ]


async def test_fetch_replay_header_returns_score_player_and_map_details() -> None:
    beatmap = await factories.create_map()
    player = await factories.create_user()
    score = await factories.create_score(
        player_id=player["id"],
        map_md5=beatmap["md5"],
    )
    scores = ScoresRepository(app.state.services.database)

    row = await scores.fetch_replay_header(score["id"])

    assert row is not None
    assert row["username"] == player["name"]
    assert row["map_md5"] == beatmap["md5"]
    assert row["artist"] == beatmap["artist"]
    assert row["title"] == beatmap["title"]
    assert row["score"] == score["score"]
