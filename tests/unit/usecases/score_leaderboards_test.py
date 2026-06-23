from __future__ import annotations

from types import SimpleNamespace
from typing import TypedDict

from app.constants.leaderboard_types import LeaderboardType
from app.constants.mods import Mods
from app.constants.scoring_metrics import ScoringMetric
from app.repositories.scores import BeatmapLeaderboardScoreRow
from app.repositories.scores import PersonalBestLeaderboardScoreRow
from app.usecases import score_leaderboards


class _LeaderboardFetch(TypedDict):
    map_md5: str
    mode: int
    user_id: int
    scoring_metric: ScoringMetric
    mods: int | None
    friend_ids: set[int] | None
    country: str | None
    limit: int


class _PersonalBestFetch(TypedDict):
    map_md5: str
    mode: int
    user_id: int
    scoring_metric: ScoringMetric


class _RankFetch(TypedDict):
    map_md5: str
    mode: int
    scoring_metric: ScoringMetric
    score: int | float


class _FakeScoresRepository:
    def __init__(
        self,
        *,
        score_rows: list[BeatmapLeaderboardScoreRow],
        personal_best_score_row: PersonalBestLeaderboardScoreRow | None = None,
        personal_best_rank: int = 1,
    ) -> None:
        self.score_rows = score_rows
        self.personal_best_score_row = personal_best_score_row
        self.personal_best_rank = personal_best_rank
        self.leaderboard_fetches: list[_LeaderboardFetch] = []
        self.personal_best_fetches: list[_PersonalBestFetch] = []
        self.rank_fetches: list[_RankFetch] = []

    async def fetch_beatmap_leaderboard_scores(
        self,
        *,
        map_md5: str,
        mode: int,
        user_id: int,
        scoring_metric: ScoringMetric,
        mods: int | None = None,
        friend_ids: set[int] | None = None,
        country: str | None = None,
        limit: int = 50,
    ) -> list[BeatmapLeaderboardScoreRow]:
        self.leaderboard_fetches.append(
            {
                "map_md5": map_md5,
                "mode": mode,
                "user_id": user_id,
                "scoring_metric": scoring_metric,
                "mods": mods,
                "friend_ids": friend_ids,
                "country": country,
                "limit": limit,
            },
        )
        return self.score_rows

    async def fetch_personal_best_leaderboard_score(
        self,
        *,
        map_md5: str,
        mode: int,
        user_id: int,
        scoring_metric: ScoringMetric,
    ) -> PersonalBestLeaderboardScoreRow | None:
        self.personal_best_fetches.append(
            {
                "map_md5": map_md5,
                "mode": mode,
                "user_id": user_id,
                "scoring_metric": scoring_metric,
            },
        )
        return self.personal_best_score_row

    async def fetch_personal_best_leaderboard_rank(
        self,
        *,
        map_md5: str,
        mode: int,
        scoring_metric: ScoringMetric,
        score: int | float,
    ) -> int:
        self.rank_fetches.append(
            {
                "map_md5": map_md5,
                "mode": mode,
                "scoring_metric": scoring_metric,
                "score": score,
            },
        )
        return self.personal_best_rank


def _beatmap_leaderboard_score(
    *,
    id: int,
    score: int | float,
) -> BeatmapLeaderboardScoreRow:
    return {
        "id": id,
        "leaderboard_value": score,
        "max_combo": 321,
        "n50": 1,
        "n100": 2,
        "n300": 300,
        "nmiss": 0,
        "nkatu": 4,
        "ngeki": 5,
        "perfect": 1,
        "mods": Mods.HIDDEN.value,
        "time": 1_704_110_400,
        "userid": 6,
        "name": "test-user",
    }


def _personal_best_leaderboard_score(
    *,
    id: int,
    score: int | float,
) -> PersonalBestLeaderboardScoreRow:
    return {
        "id": id,
        "leaderboard_value": score,
        "max_combo": 321,
        "n50": 1,
        "n100": 2,
        "n300": 300,
        "nmiss": 0,
        "nkatu": 4,
        "ngeki": 5,
        "perfect": 1,
        "mods": Mods.HIDDEN.value,
        "time": 1_704_110_400,
    }


async def test_fetch_leaderboard_scores_fetches_personal_best_rank() -> None:
    player = SimpleNamespace(
        id=6,
        friends={7, 8},
        geoloc={"country": {"acronym": "ca"}},
    )
    score_row = _beatmap_leaderboard_score(id=10, score=500_000)
    personal_best_score_row = _personal_best_leaderboard_score(
        id=11,
        score=450_000,
    )
    scores = _FakeScoresRepository(
        score_rows=[score_row],
        personal_best_score_row=personal_best_score_row,
        personal_best_rank=3,
    )

    result = await score_leaderboards.fetch_leaderboard_scores(
        leaderboard_type=LeaderboardType.Top,
        map_md5="map-md5",
        mode=0,
        mods=Mods.HIDDEN,
        player=player,
        scoring_metric="score",
        scores=scores,
    )

    assert result.score_rows == [score_row]
    assert result.personal_best_score_row == {
        **personal_best_score_row,
        "rank": 3,
    }
    assert scores.leaderboard_fetches == [
        {
            "map_md5": "map-md5",
            "mode": 0,
            "user_id": 6,
            "scoring_metric": "score",
            "mods": None,
            "friend_ids": None,
            "country": None,
            "limit": 50,
        },
    ]
    assert scores.personal_best_fetches == [
        {
            "map_md5": "map-md5",
            "mode": 0,
            "user_id": 6,
            "scoring_metric": "score",
        },
    ]
    assert scores.rank_fetches == [
        {
            "map_md5": "map-md5",
            "mode": 0,
            "scoring_metric": "score",
            "score": 450_000,
        },
    ]


async def test_fetch_leaderboard_scores_skips_personal_best_when_empty() -> None:
    player = SimpleNamespace(
        id=6,
        friends={7, 8},
        geoloc={"country": {"acronym": "ca"}},
    )
    scores = _FakeScoresRepository(score_rows=[])

    result = await score_leaderboards.fetch_leaderboard_scores(
        leaderboard_type=LeaderboardType.Top,
        map_md5="map-md5",
        mode=0,
        mods=Mods.HIDDEN,
        player=player,
        scoring_metric="score",
        scores=scores,
    )

    assert result.score_rows == []
    assert result.personal_best_score_row is None
    assert scores.personal_best_fetches == []
    assert scores.rank_fetches == []


async def test_fetch_leaderboard_scores_applies_mods_filter() -> None:
    player = SimpleNamespace(
        id=6,
        friends={7, 8},
        geoloc={"country": {"acronym": "ca"}},
    )
    scores = _FakeScoresRepository(
        score_rows=[_beatmap_leaderboard_score(id=10, score=123.45)],
    )

    await score_leaderboards.fetch_leaderboard_scores(
        leaderboard_type=LeaderboardType.Mods,
        map_md5="map-md5",
        mode=4,
        mods=Mods.HIDDEN | Mods.RELAX,
        player=player,
        scoring_metric="pp",
        scores=scores,
    )

    assert scores.leaderboard_fetches[0]["mods"] == (Mods.HIDDEN | Mods.RELAX).value
    assert scores.leaderboard_fetches[0]["friend_ids"] is None
    assert scores.leaderboard_fetches[0]["country"] is None


async def test_fetch_leaderboard_scores_applies_friends_filter() -> None:
    player = SimpleNamespace(
        id=6,
        friends={7, 8},
        geoloc={"country": {"acronym": "ca"}},
    )
    scores = _FakeScoresRepository(
        score_rows=[_beatmap_leaderboard_score(id=10, score=123.45)],
    )

    await score_leaderboards.fetch_leaderboard_scores(
        leaderboard_type=LeaderboardType.Friends,
        map_md5="map-md5",
        mode=4,
        mods=Mods.HIDDEN | Mods.RELAX,
        player=player,
        scoring_metric="pp",
        scores=scores,
    )

    assert scores.leaderboard_fetches[0]["mods"] is None
    assert scores.leaderboard_fetches[0]["friend_ids"] == {6, 7, 8}
    assert scores.leaderboard_fetches[0]["country"] is None


async def test_fetch_leaderboard_scores_applies_country_filter() -> None:
    player = SimpleNamespace(
        id=6,
        friends={7, 8},
        geoloc={"country": {"acronym": "ca"}},
    )
    scores = _FakeScoresRepository(
        score_rows=[_beatmap_leaderboard_score(id=10, score=123.45)],
    )

    await score_leaderboards.fetch_leaderboard_scores(
        leaderboard_type=LeaderboardType.Country,
        map_md5="map-md5",
        mode=4,
        mods=Mods.HIDDEN | Mods.RELAX,
        player=player,
        scoring_metric="pp",
        scores=scores,
    )

    assert scores.leaderboard_fetches[0]["mods"] is None
    assert scores.leaderboard_fetches[0]["friend_ids"] is None
    assert scores.leaderboard_fetches[0]["country"] == "ca"
