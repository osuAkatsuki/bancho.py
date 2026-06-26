from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import dataclass
from enum import StrEnum
from typing import NotRequired
from typing import Protocol
from typing import TypedDict

from app.constants.beatmap_statuses import RankedStatus


class DirectSearchParams(TypedDict):
    amount: int
    offset: int
    query: NotRequired[str]
    mode: NotRequired[int]
    status: NotRequired[int]


class DirectSearchBeatmapPayload(TypedDict):
    DifficultyRating: float
    DiffName: str
    CS: float
    OD: float
    AR: float
    HP: float
    Mode: int


class DirectSearchSetPayload(TypedDict):
    Artist: str
    Title: str
    Creator: str
    RankedStatus: int
    LastUpdate: str
    SetID: int
    HasVideo: bool | int
    ChildrenBeatmaps: list[DirectSearchBeatmapPayload] | None


class DirectSearchHTTPResponse(Protocol):
    status_code: int

    def json(self) -> list[DirectSearchSetPayload]: ...


class DirectSearchGetter(Protocol):
    def __call__(
        self,
        url: str,
        *,
        params: DirectSearchParams,
    ) -> Awaitable[DirectSearchHTTPResponse]: ...


@dataclass(frozen=True)
class DirectSearchBeatmap:
    difficulty_rating: float
    name: str
    cs: float
    od: float
    ar: float
    hp: float
    mode: int


@dataclass(frozen=True)
class DirectSearchSet:
    artist: str
    title: str
    creator: str
    ranked_status: int
    last_update: str
    set_id: int
    has_video: int
    beatmaps: list[DirectSearchBeatmap]


class DirectSearchResultCode(StrEnum):
    FOUND = "found"
    MIRROR_ERROR = "mirror_error"


@dataclass(frozen=True)
class DirectSearchResult:
    code: DirectSearchResultCode
    result_count: int = 0
    beatmap_sets: list[DirectSearchSet] | None = None


@dataclass(frozen=True)
class DirectSearchService:
    mirror_search_endpoint: str
    fetch_mirror_search: DirectSearchGetter

    async def search(
        self,
        *,
        ranked_status: int,
        query: str,
        mode: int,
        page_num: int,
    ) -> DirectSearchResult:
        params: DirectSearchParams = {
            "amount": 100,
            "offset": page_num * 100,
        }

        # eventually we could try supporting these,
        # but it mostly depends on the mirror.
        if query not in ("Newest", "Top+Rated", "Most+Played"):
            params["query"] = query

        if mode != -1:  # -1 for all
            params["mode"] = mode

        if ranked_status != 4:  # 4 for all
            # convert to osu!api status
            params["status"] = RankedStatus.from_osudirect(ranked_status).osu_api

        response = await self.fetch_mirror_search(
            self.mirror_search_endpoint,
            params=params,
        )
        if response.status_code != 200:
            return DirectSearchResult(code=DirectSearchResultCode.MIRROR_ERROR)

        result = response.json()
        beatmap_sets: list[DirectSearchSet] = []

        for bmapset in result:
            if bmapset["ChildrenBeatmaps"] is None:
                continue

            diff_sorted_maps = sorted(
                bmapset["ChildrenBeatmaps"],
                key=lambda beatmap: beatmap["DifficultyRating"],
            )

            beatmap_sets.append(
                DirectSearchSet(
                    artist=self._replace_osudirect_delimiter(bmapset["Artist"]),
                    title=self._replace_osudirect_delimiter(bmapset["Title"]),
                    creator=bmapset["Creator"],
                    ranked_status=bmapset["RankedStatus"],
                    last_update=bmapset["LastUpdate"],
                    set_id=bmapset["SetID"],
                    # some mirrors use a true/false instead of 0 or 1
                    has_video=int(bmapset["HasVideo"]),
                    beatmaps=[
                        DirectSearchBeatmap(
                            difficulty_rating=beatmap["DifficultyRating"],
                            name=self._replace_osudirect_delimiter(
                                beatmap["DiffName"],
                            ),
                            cs=beatmap["CS"],
                            od=beatmap["OD"],
                            ar=beatmap["AR"],
                            hp=beatmap["HP"],
                            mode=beatmap["Mode"],
                        )
                        for beatmap in diff_sorted_maps
                    ],
                ),
            )

        result_count = len(result)
        return DirectSearchResult(
            code=DirectSearchResultCode.FOUND,
            # send over 100 if we receive 100 matches, so the client knows
            # there are more to get.
            result_count=101 if result_count == 100 else result_count,
            beatmap_sets=beatmap_sets,
        )

    def _replace_osudirect_delimiter(self, value: str) -> str:
        # XXX: this is a bug that exists on official servers (lmao)
        # | is used to delimit the set data, so the difficulty name
        # cannot contain this or it will be ignored. we fix it here
        # by using a different character.
        return value.replace("|", "I")
