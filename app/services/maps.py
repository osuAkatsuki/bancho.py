from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from app.constants.beatmap_statuses import RankedStatus
from app.constants.score_statuses import SubmissionStatus
from app.objects.beatmap import Beatmap
from app.repositories.maps import Map
from app.repositories.maps import MapSetInfo
from app.repositories.maps import MapsRepository
from app.repositories.ratings import RatingsRepository
from app.repositories.scores import ScoresRepository


@dataclass(frozen=True)
class MapsListing:
    maps: list[Map]
    total_maps: int


@dataclass(frozen=True)
class MapsService:
    maps: MapsRepository

    async def fetch_maps(
        self,
        *,
        set_id: int | None,
        server: str | None,
        status: int | None,
        artist: str | None,
        creator: str | None,
        filename: str | None,
        mode: int | None,
        frozen: bool | None,
        page: int,
        page_size: int,
    ) -> MapsListing:
        maps = await self.maps.fetch_many(
            server=server,
            set_id=set_id,
            status=status,
            artist=artist,
            creator=creator,
            filename=filename,
            mode=mode,
            frozen=frozen,
            page=page,
            page_size=page_size,
        )
        total_maps = await self.maps.fetch_count(
            server=server,
            set_id=set_id,
            status=status,
            artist=artist,
            creator=creator,
            filename=filename,
            mode=mode,
            frozen=frozen,
        )

        return MapsListing(maps=maps, total_maps=total_maps)

    async def fetch_map(self, map_id: int) -> Map | None:
        return await self.maps.fetch_one(id=map_id)


@dataclass(frozen=True)
class BeatmapInfo:
    index: int
    id: int
    set_id: int
    md5: str
    status: int
    grades: list[str]


@dataclass(frozen=True)
class BeatmapInfoService:
    maps: MapsRepository
    scores: ScoresRepository

    async def fetch_beatmap_info(
        self,
        *,
        filenames: Sequence[str],
        player_id: int,
        vanilla_mode: int,
    ) -> list[BeatmapInfo]:
        beatmap_info: list[BeatmapInfo] = []

        for idx, map_filename in enumerate(filenames):
            beatmap = await self.maps.fetch_one(filename=map_filename)
            if beatmap is None:
                continue

            # osu! only allows us to send back one grade per gamemode, so we
            # send back vanilla grades. In theory this could be user-customizable.
            grades = ["N", "N", "N", "N"]
            for score in await self.scores.fetch_many(
                map_md5=beatmap["md5"],
                user_id=player_id,
                mode=vanilla_mode,
                status=SubmissionStatus.BEST,
            ):
                grades[score["mode"]] = score["grade"]

            beatmap_info.append(
                BeatmapInfo(
                    index=idx,
                    id=beatmap["id"],
                    set_id=beatmap["set_id"],
                    md5=beatmap["md5"],
                    status=beatmap["status"],
                    grades=grades,
                ),
            )

        return beatmap_info


class BeatmapRatingResultCode(StrEnum):
    NO_EXIST = "no_exist"
    NOT_RANKED = "not_ranked"
    CAN_RATE = "can_rate"
    ALREADY_VOTED = "already_voted"


@dataclass(frozen=True)
class BeatmapRatingResult:
    code: BeatmapRatingResultCode
    average_rating: float | None = None


@dataclass(frozen=True)
class BeatmapRatingService:
    ratings: RatingsRepository
    beatmap_cache: Mapping[str | int, Beatmap]

    async def rate_or_check(
        self,
        *,
        player_id: int,
        map_md5: str,
        rating: int | None,
    ) -> BeatmapRatingResult:
        if rating is None:
            if map_md5 not in self.beatmap_cache:
                return BeatmapRatingResult(code=BeatmapRatingResultCode.NO_EXIST)

            cached = self.beatmap_cache[map_md5]
            if cached.status < RankedStatus.Ranked:
                return BeatmapRatingResult(code=BeatmapRatingResultCode.NOT_RANKED)

            existing_rating = await self.ratings.fetch_one(
                map_md5=map_md5,
                userid=player_id,
            )
            if existing_rating is None:
                return BeatmapRatingResult(code=BeatmapRatingResultCode.CAN_RATE)
        else:
            await self.ratings.create(
                userid=player_id,
                map_md5=map_md5,
                rating=rating,
            )

        map_ratings = await self.ratings.fetch_many(map_md5=map_md5)
        ratings = [row["rating"] for row in map_ratings]
        return BeatmapRatingResult(
            code=BeatmapRatingResultCode.ALREADY_VOTED,
            average_rating=sum(ratings) / len(ratings),
        )


@dataclass(frozen=True)
class BeatmapSetService:
    maps: MapsRepository

    async def fetch_set_info(
        self,
        *,
        set_id: int | None = None,
        map_id: int | None = None,
        md5: str | None = None,
    ) -> MapSetInfo | None:
        return await self.maps.fetch_set_info(
            set_id=set_id,
            map_id=map_id,
            md5=md5,
        )
