from __future__ import annotations

from types import SimpleNamespace

from app.constants.beatmap_statuses import RankedStatus
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.services import osu_web


class _DirectSearchResponse:
    def __init__(
        self,
        *,
        status_code: int,
        payload: list[osu_web.DirectSearchSetPayload],
    ) -> None:
        self.status_code = status_code
        self.payload = payload

    def json(self) -> list[osu_web.DirectSearchSetPayload]:
        return self.payload


class _DirectSearchFetcher:
    def __init__(self, response: _DirectSearchResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, osu_web.DirectSearchParams]] = []

    async def __call__(
        self,
        url: str,
        *,
        params: osu_web.DirectSearchParams,
    ) -> _DirectSearchResponse:
        self.calls.append((url, params))
        return self.response


class _FakeScoresService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def fetch_leaderboard_scores(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(
            score_rows=[
                {
                    "id": 10,
                    "leaderboard_value": 987.6,
                    "max_combo": 321,
                    "n50": 1,
                    "n100": 2,
                    "n300": 300,
                    "nmiss": 0,
                    "nkatu": 4,
                    "ngeki": 5,
                    "perfect": 1,
                    "mods": Mods.RELAX.value,
                    "time": 1_704_110_400,
                    "userid": 6,
                    "name": "score-user",
                },
            ],
            personal_best_score_row={
                "id": 11,
                "leaderboard_value": 543.2,
                "max_combo": 123,
                "n50": 1,
                "n100": 2,
                "n300": 300,
                "nmiss": 0,
                "nkatu": 4,
                "ngeki": 5,
                "perfect": 1,
                "mods": Mods.RELAX.value,
                "time": 1_704_110_400,
                "rank": 7,
            },
        )


class _FakeClans:
    async def fetch_one(self, *, id: int) -> dict[str, str] | None:
        return {"tag": "AK"} if id == 123 else None


class _FakeMaps:
    def __init__(self, *, filename_exists: bool = False) -> None:
        self.filename_exists = filename_exists

    async def fetch_one(
        self,
        *,
        filename: str,
    ) -> dict[str, object] | None:
        return {"filename": filename} if self.filename_exists else None


class _FakeRatings:
    async def fetch_many(
        self,
        *,
        map_md5: str,
        page: int | None,
        page_size: int | None,
    ) -> list[dict[str, int]]:
        return [{"rating": 8}, {"rating": 10}]


async def _record_strange_occurrence(obj: object) -> None:
    pass


def _stacktrace() -> object:
    return []


def _leaderboard_service(
    *,
    score_leaderboards: object | None = None,
    fetch_beatmap: object | None = None,
    unsubmitted_cache: set[str] | None = None,
    needs_update_cache: set[str] | None = None,
    beatmapset_cache: dict[int, object] | None = None,
    maps: object | None = None,
    published_stats: list[object] | None = None,
) -> osu_web.OsuLeaderboardService:
    if score_leaderboards is None:
        score_leaderboards = _FakeScoresService()
    if fetch_beatmap is None:

        async def fetch_beatmap(md5: str, set_id: int = -1) -> object | None:
            return None

    if unsubmitted_cache is None:
        unsubmitted_cache = set()
    if needs_update_cache is None:
        needs_update_cache = set()
    if beatmapset_cache is None:
        beatmapset_cache = {}
    if maps is None:
        maps = _FakeMaps()
    if published_stats is None:
        published_stats = []

    return osu_web.OsuLeaderboardService(
        score_leaderboards=score_leaderboards,
        clans=_FakeClans(),
        maps=maps,
        ratings=_FakeRatings(),
        beatmap_fetcher=fetch_beatmap,
        unsubmitted_cache=unsubmitted_cache,
        needs_update_cache=needs_update_cache,
        beatmapset_cache=beatmapset_cache,
        publish_user_stats=published_stats.append,
        increment_metric=lambda metric: None,
        log_strange_occurrence=_record_strange_occurrence,
        get_appropriate_stacktrace=_stacktrace,
    )


async def test_direct_search_normalizes_mirror_response() -> None:
    response = _DirectSearchResponse(
        status_code=200,
        payload=[
            {
                "Artist": "A|rtist",
                "Title": "Title",
                "Creator": "Creator",
                "RankedStatus": 1,
                "LastUpdate": "2024-01-01",
                "SetID": 123,
                "HasVideo": True,
                "ChildrenBeatmaps": [
                    {
                        "DifficultyRating": 5.0,
                        "DiffName": "Hard|Pipe",
                        "CS": 4.0,
                        "OD": 8.0,
                        "AR": 9.0,
                        "HP": 6.5,
                        "Mode": 0,
                    },
                    {
                        "DifficultyRating": 2.5,
                        "DiffName": "Normal",
                        "CS": 3.0,
                        "OD": 6.0,
                        "AR": 7.0,
                        "HP": 4.5,
                        "Mode": 0,
                    },
                ],
            },
            {
                "Artist": "Skipped",
                "Title": "No children",
                "Creator": "Creator",
                "RankedStatus": 1,
                "LastUpdate": "2024-01-01",
                "SetID": 124,
                "HasVideo": False,
                "ChildrenBeatmaps": None,
            },
        ],
    )
    fetcher = _DirectSearchFetcher(response)
    service = osu_web.DirectSearchService(
        mirror_search_endpoint="https://mirror.test/search",
        fetch_mirror_search=fetcher,
    )

    result = await service.search(
        ranked_status=0,
        query="camellia",
        mode=0,
        page_num=2,
    )

    assert result.code is osu_web.DirectSearchResultCode.FOUND
    assert result.result_count == 2
    assert fetcher.calls == [
        (
            "https://mirror.test/search",
            {"amount": 100, "offset": 200, "query": "camellia", "mode": 0, "status": 1},
        ),
    ]
    assert result.beatmap_sets is not None
    assert len(result.beatmap_sets) == 1
    beatmap_set = result.beatmap_sets[0]
    assert beatmap_set.artist == "AIrtist"
    assert beatmap_set.has_video == 1
    assert [beatmap.name for beatmap in beatmap_set.beatmaps] == [
        "Normal",
        "HardIPipe",
    ]


async def test_osu_leaderboard_service_marks_known_filename_as_needing_update() -> None:
    needs_update_cache: set[str] = set()
    unsubmitted_cache: set[str] = set()
    service = _leaderboard_service(
        unsubmitted_cache=unsubmitted_cache,
        needs_update_cache=needs_update_cache,
        beatmapset_cache={
            123: SimpleNamespace(
                maps=[SimpleNamespace(filename="Artist - Title [Hard].osu")],
            ),
        },
    )
    player = SimpleNamespace(
        status=SimpleNamespace(mode=GameMode.VANILLA_OSU, mods=Mods.NOMOD),
        restricted=False,
    )

    result = await service.fetch_leaderboard(
        player=player,
        request=osu_web.OsuLeaderboardRequest(
            requesting_from_editor_song_select=False,
            leaderboard_type=0,
            map_md5="missing-md5",
            map_filename="Artist+-+Title+%5BHard%5D.osu",
            mode_arg=0,
            map_set_id=123,
            mods_arg=0,
            aqn_files_found=False,
        ),
    )

    assert result.code is osu_web.OsuLeaderboardResultCode.NEEDS_UPDATE
    assert needs_update_cache == {"missing-md5"}
    assert unsubmitted_cache == set()


async def test_osu_leaderboard_service_fetches_ranked_relax_leaderboard() -> None:
    async def fetch_beatmap(md5: str, set_id: int = -1) -> object | None:
        return SimpleNamespace(
            id=321,
            set_id=654,
            md5=md5,
            status=RankedStatus.Ranked,
            full_name="Artist - Title [Hard]",
        )

    score_leaderboards = _FakeScoresService()
    published_stats: list[object] = []
    service = _leaderboard_service(
        score_leaderboards=score_leaderboards,
        fetch_beatmap=fetch_beatmap,
        published_stats=published_stats,
    )
    player = SimpleNamespace(
        id=6,
        name="cmyui",
        clan_id=123,
        status=SimpleNamespace(mode=GameMode.VANILLA_OSU, mods=Mods.NOMOD),
        restricted=False,
    )

    result = await service.fetch_leaderboard(
        player=player,
        request=osu_web.OsuLeaderboardRequest(
            requesting_from_editor_song_select=False,
            leaderboard_type=0,
            map_md5="ranked-md5",
            map_filename="Artist - Title [Hard].osu",
            mode_arg=0,
            map_set_id=654,
            mods_arg=Mods.RELAX.value,
            aqn_files_found=False,
        ),
    )

    assert result.code is osu_web.OsuLeaderboardResultCode.FOUND
    assert result.beatmap_rating == 9.0
    assert result.personal_best_display_name == "[AK] cmyui"
    assert result.personal_best_user_id == 6
    assert player.status.mode == GameMode.RELAX_OSU
    assert player.status.mods == Mods.RELAX
    assert published_stats == [player]
    assert score_leaderboards.calls[0]["mode"] == GameMode.RELAX_OSU
    assert score_leaderboards.calls[0]["mods"] == Mods.RELAX
    assert score_leaderboards.calls[0]["scoring_metric"] == "pp"


async def test_screenshot_service_rejects_invalid_file_type(tmp_path) -> None:
    service = osu_web.ScreenshotService(
        screenshots_path=tmp_path,
        token_urlsafe=lambda size: "token",
        log_strange_occurrence=_record_strange_occurrence,
    )

    result = await service.upload_screenshot(
        player=SimpleNamespace(),
        endpoint_version=1,
        screenshot_data=b"not an image",
    )

    assert result.code is osu_web.ScreenshotUploadResultCode.INVALID_FILE_TYPE
    assert list(tmp_path.iterdir()) == []


async def test_screenshot_service_writes_png_file(tmp_path) -> None:
    service = osu_web.ScreenshotService(
        screenshots_path=tmp_path,
        token_urlsafe=lambda size: "token",
        log_strange_occurrence=_record_strange_occurrence,
    )
    png_data = b"\x89PNG\r\n\x1a\n" + b"image bytes" + b"\x49END\xae\x42\x60\x82"

    result = await service.upload_screenshot(
        player=SimpleNamespace(),
        endpoint_version=1,
        screenshot_data=png_data,
    )

    assert result == osu_web.ScreenshotUploadResult(
        code=osu_web.ScreenshotUploadResultCode.UPLOADED,
        filename="token.png",
    )
    assert (tmp_path / "token.png").read_bytes() == png_data
