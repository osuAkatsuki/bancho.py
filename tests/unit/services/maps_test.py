from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import app.services.maps as maps
from app.constants.beatmap_statuses import RankedStatus
from app.constants.score_statuses import SubmissionStatus
from app.repositories.maps import Map
from app.repositories.ratings import Rating
from app.repositories.scores import Score


class _FakeMapsRepository:
    async def fetch_one(
        self,
        *,
        filename: str | None = None,
        id: int | None = None,
    ) -> Map | None:
        if filename == "Artist - Title [Hard].osu":
            return Map(
                id=1,
                server="osu!",
                set_id=2,
                status=RankedStatus.Ranked,
                md5="md5",
                artist="Artist",
                title="Title",
                version="Hard",
                creator="creator",
                filename=filename,
                last_update=datetime(2024, 1, 1),
                total_length=120,
                max_combo=500,
                frozen=False,
                plays=0,
                passes=0,
                mode=0,
                bpm=180.0,
                cs=4.0,
                ar=9.0,
                od=8.0,
                hp=6.0,
                diff=5.0,
            )

        return None


class _FakeScoresRepository:
    async def fetch_many(
        self,
        *,
        map_md5: str,
        user_id: int,
        mode: int,
        status: SubmissionStatus,
    ) -> list[Score]:
        return [
            Score(
                id=1,
                map_md5=map_md5,
                score=1_000_000,
                pp=100.0,
                acc=98.0,
                max_combo=500,
                mods=0,
                n300=300,
                n100=0,
                n50=0,
                nmiss=0,
                ngeki=0,
                nkatu=0,
                grade="A",
                status=status.value,
                mode=0,
                play_time=datetime(2024, 1, 1),
                time_elapsed=60_000,
                client_flags=0,
                userid=user_id,
                perfect=1,
                online_checksum="checksum-1",
            ),
            Score(
                id=2,
                map_md5=map_md5,
                score=900_000,
                pp=90.0,
                acc=96.0,
                max_combo=450,
                mods=0,
                n300=290,
                n100=10,
                n50=0,
                nmiss=0,
                ngeki=0,
                nkatu=0,
                grade="S",
                status=status.value,
                mode=2,
                play_time=datetime(2024, 1, 1),
                time_elapsed=60_000,
                client_flags=0,
                userid=user_id,
                perfect=0,
                online_checksum="checksum-2",
            ),
        ]


class _FakeRatingsRepository:
    def __init__(self) -> None:
        self.created_ratings: list[dict[str, object]] = []

    async def fetch_one(self, *, map_md5: str, userid: int) -> object | None:
        return None

    async def create(self, **rating: object) -> None:
        self.created_ratings.append(rating)

    async def fetch_many(self, *, map_md5: str) -> list[Rating]:
        return [
            Rating(userid=1, map_md5=map_md5, rating=7),
            Rating(userid=2, map_md5=map_md5, rating=9),
        ]


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
