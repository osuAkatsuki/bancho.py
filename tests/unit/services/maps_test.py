from __future__ import annotations

from types import SimpleNamespace

import app.services.maps as maps
from app.constants.beatmap_statuses import RankedStatus
from app.constants.score_statuses import SubmissionStatus


class _FakeMapsRepository:
    async def fetch_one(
        self,
        *,
        filename: str | None = None,
        id: int | None = None,
    ) -> dict[str, object] | None:
        if filename == "Artist - Title [Hard].osu":
            return {
                "id": 1,
                "set_id": 2,
                "md5": "md5",
                "status": RankedStatus.Ranked,
            }

        return None


class _FakeScoresRepository:
    async def fetch_many(
        self,
        *,
        map_md5: str,
        user_id: int,
        mode: int,
        status: SubmissionStatus,
    ) -> list[dict[str, object]]:
        return [
            {"mode": 0, "grade": "A"},
            {"mode": 2, "grade": "S"},
        ]


class _FakeRatingsRepository:
    def __init__(self) -> None:
        self.created_ratings: list[dict[str, object]] = []

    async def fetch_one(self, *, map_md5: str, userid: int) -> object | None:
        return None

    async def create(self, **rating: object) -> None:
        self.created_ratings.append(rating)

    async def fetch_many(self, *, map_md5: str) -> list[dict[str, int]]:
        return [{"rating": 7}, {"rating": 9}]


async def test_beatmap_info_service_returns_vanilla_grades_by_filename() -> None:
    service = maps.BeatmapInfoService(
        maps=_FakeMapsRepository(),
        scores=_FakeScoresRepository(),
    )

    beatmap_info = await service.fetch_beatmap_info(
        filenames=["missing.osu", "Artist - Title [Hard].osu"],
        player_id=5,
        vanilla_mode=0,
    )

    assert beatmap_info == [
        maps.BeatmapInfo(
            index=1,
            id=1,
            set_id=2,
            md5="md5",
            status=RankedStatus.Ranked,
            grades=["A", "N", "S", "N"],
        ),
    ]


async def test_beatmap_rating_service_creates_rating_and_returns_average() -> None:
    ratings = _FakeRatingsRepository()
    service = maps.BeatmapRatingService(
        ratings=ratings,
        beatmap_cache={"md5": SimpleNamespace(status=RankedStatus.Ranked)},
    )

    result = await service.rate_or_check(player_id=5, map_md5="md5", rating=10)

    assert result == maps.BeatmapRatingResult(
        code=maps.BeatmapRatingResultCode.ALREADY_VOTED,
        average_rating=8.0,
    )
    assert ratings.created_ratings == [
        {"userid": 5, "map_md5": "md5", "rating": 10},
    ]
