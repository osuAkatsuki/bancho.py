from __future__ import annotations

from types import SimpleNamespace

import app.services.beatmap_leaderboards as beatmap_leaderboards
from app.constants.beatmap_statuses import RankedStatus
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods


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
) -> beatmap_leaderboards.BeatmapLeaderboardService:
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

    return beatmap_leaderboards.BeatmapLeaderboardService(
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


async def test_beatmap_leaderboard_marks_known_filename_needs_update() -> None:
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
        request=beatmap_leaderboards.BeatmapLeaderboardRequest(
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

    assert result.code is beatmap_leaderboards.BeatmapLeaderboardResultCode.NEEDS_UPDATE
    assert needs_update_cache == {"missing-md5"}
    assert unsubmitted_cache == set()


async def test_beatmap_leaderboard_service_fetches_ranked_relax_leaderboard() -> None:
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
        request=beatmap_leaderboards.BeatmapLeaderboardRequest(
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

    assert result.code is beatmap_leaderboards.BeatmapLeaderboardResultCode.FOUND
    assert result.beatmap_rating == 9.0
    assert result.personal_best_display_name == "[AK] cmyui"
    assert result.personal_best_user_id == 6
    assert player.status.mode == GameMode.RELAX_OSU
    assert player.status.mods == Mods.RELAX
    assert published_stats == [player]
    assert score_leaderboards.calls[0]["mode"] == GameMode.RELAX_OSU
    assert score_leaderboards.calls[0]["mods"] == Mods.RELAX
    assert score_leaderboards.calls[0]["scoring_metric"] == "pp"
