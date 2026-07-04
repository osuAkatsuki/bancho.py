from __future__ import annotations

from datetime import datetime

import app.services.scores as scores
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.objects.beatmap import Beatmap
from app.objects.beatmap import BeatmapSet
from app.repositories.scores import MapScoreListingRow
from app.repositories.scores import MostPlayedMapRow
from app.repositories.scores import PlayerScoreListingRow
from app.repositories.scores import ReplayHeader
from app.repositories.scores import Score


class _FakeScoresRepository:
    def __init__(self) -> None:
        self.player_score_calls: list[dict[str, object | None]] = []
        self.map_score_calls: list[dict[str, object | None]] = []

    async def fetch_count(
        self,
        map_md5: str | None = None,
        mods: int | None = None,
        status: int | None = None,
        mode: int | None = None,
        user_id: int | None = None,
    ) -> int:
        return 0

    async def fetch_many(
        self,
        map_md5: str | None = None,
        mods: int | None = None,
        status: int | None = None,
        mode: int | None = None,
        user_id: int | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> list[Score]:
        return []

    async def fetch_one(self, id: int) -> Score | None:
        return Score(
            id=id,
            map_md5="map-md5",
            score=1_000_000,
            pp=123.45,
            acc=98.76,
            max_combo=321,
            mods=Mods.HIDDEN.value,
            n300=300,
            n100=5,
            n50=1,
            nmiss=0,
            ngeki=0,
            nkatu=0,
            grade="A",
            status=2,
            mode=4,
            play_time=datetime(2024, 1, 1),
            time_elapsed=60_000,
            client_flags=0,
            userid=3,
            perfect=1,
            online_checksum="checksum",
        )

    async def fetch_player_score_listing_rows(
        self,
        *,
        user_id: int,
        mode: int,
        mods: int | None,
        strong_mods_equality: bool,
        scope: str,
        limit: int,
        include_loved: bool,
        include_failed: bool,
    ) -> list[PlayerScoreListingRow]:
        self.player_score_calls.append(
            {
                "user_id": user_id,
                "mode": mode,
                "mods": mods,
                "strong_mods_equality": strong_mods_equality,
                "scope": scope,
                "limit": limit,
                "include_loved": include_loved,
                "include_failed": include_failed,
            },
        )
        return [
            PlayerScoreListingRow(
                id=1,
                map_md5="known-map",
                score=1_000_000,
                pp=123.45,
                acc=98.76,
                max_combo=321,
                mods=Mods.HIDDEN.value,
                n300=300,
                n100=5,
                n50=1,
                nmiss=0,
                ngeki=0,
                nkatu=0,
                grade="A",
                status=2,
                mode=4,
                play_time=datetime(2024, 1, 1),
                time_elapsed=60_000,
                perfect=1,
            ),
            PlayerScoreListingRow(
                id=2,
                map_md5="missing-map",
                score=500_000,
                pp=50.0,
                acc=90.0,
                max_combo=123,
                mods=0,
                n300=250,
                n100=25,
                n50=5,
                nmiss=2,
                ngeki=0,
                nkatu=0,
                grade="B",
                status=2,
                mode=4,
                play_time=datetime(2024, 1, 2),
                time_elapsed=60_000,
                perfect=0,
            ),
        ]

    async def fetch_map_score_listing_rows(
        self,
        *,
        map_md5: str,
        mode: int,
        mods: int | None,
        strong_mods_equality: bool,
        scope: str,
        limit: int,
    ) -> list[MapScoreListingRow]:
        self.map_score_calls.append(
            {
                "map_md5": map_md5,
                "mode": mode,
                "mods": mods,
                "strong_mods_equality": strong_mods_equality,
                "scope": scope,
                "limit": limit,
            },
        )
        return [
            MapScoreListingRow(
                id=1,
                map_md5=map_md5,
                score=123,
                pp=12.3,
                acc=98.0,
                max_combo=100,
                mods=0,
                n300=300,
                n100=0,
                n50=0,
                nmiss=0,
                ngeki=0,
                nkatu=0,
                grade="A",
                status=2,
                mode=mode,
                play_time=datetime(2024, 1, 1),
                time_elapsed=60_000,
                userid=3,
                perfect=1,
                player_name="player",
                player_country="CA",
                clan_id=None,
                clan_name=None,
                clan_tag=None,
            ),
        ]

    async def fetch_most_played_map_rows(
        self,
        *,
        user_id: int,
        mode: int,
        limit: int,
    ) -> list[MostPlayedMapRow]:
        return [
            MostPlayedMapRow(
                md5="map-md5",
                id=1,
                set_id=2,
                status=2,
                artist="Artist",
                title="Title",
                version="Hard",
                creator="creator",
                plays=limit,
            ),
        ]

    async def fetch_replay_header(self, score_id: int) -> ReplayHeader | None:
        return ReplayHeader(
            username="player",
            map_md5="map-md5",
            artist="Artist",
            title="Title",
            version="Hard",
            mode=0,
            n300=300,
            n100=0,
            n50=0,
            ngeki=0,
            nkatu=0,
            nmiss=0,
            score=score_id,
            max_combo=100,
            perfect=1,
            mods=0,
            play_time=datetime(2024, 1, 1),
        )


class _FakeBeatmapFetcher:
    def __init__(self) -> None:
        self.md5s: list[str] = []
        self.known_beatmap = Beatmap(
            map_set=BeatmapSet(id=1, last_osuapi_check=datetime(2024, 1, 1)),
            md5="known-map",
            id=1,
        )

    async def __call__(
        self,
        md5: str,
        set_id: int = -1,
    ) -> Beatmap | None:
        self.md5s.append(md5)
        if md5 == "known-map":
            return self.known_beatmap

        return None


class _FakeUsersRepository:
    async def fetch_one(self, id: int | None = None) -> None:
        return None


class _FakeClansRepository:
    async def fetch_one(self, id: int | None = None) -> None:
        return None


def _service() -> (
    tuple[scores.ScoresService, _FakeScoresRepository, _FakeBeatmapFetcher]
):
    scores_repo = _FakeScoresRepository()
    beatmap_fetcher = _FakeBeatmapFetcher()
    return (
        scores.ScoresService(
            scores=scores_repo,
            users=_FakeUsersRepository(),
            clans=_FakeClansRepository(),
            fetch_beatmap=beatmap_fetcher,
        ),
        scores_repo,
        beatmap_fetcher,
    )


async def test_scores_service_attaches_beatmaps_to_player_score_rows() -> None:
    service, scores_repo, beatmap_fetcher = _service()

    rows = await service.fetch_player_scores(
        player_id=3,
        mode=GameMode.RELAX_OSU,
        mods=Mods.HIDDEN,
        strong_mods_equality=True,
        scope="best",
        limit=50,
        include_loved=True,
        include_failed=False,
    )

    assert rows == [
        scores.PlayerScoreWithBeatmap(
            score=PlayerScoreListingRow(
                id=1,
                map_md5="known-map",
                score=1_000_000,
                pp=123.45,
                acc=98.76,
                max_combo=321,
                mods=Mods.HIDDEN.value,
                n300=300,
                n100=5,
                n50=1,
                nmiss=0,
                ngeki=0,
                nkatu=0,
                grade="A",
                status=2,
                mode=4,
                play_time=datetime(2024, 1, 1),
                time_elapsed=60_000,
                perfect=1,
            ),
            beatmap=beatmap_fetcher.known_beatmap,
        ),
        scores.PlayerScoreWithBeatmap(
            score=PlayerScoreListingRow(
                id=2,
                map_md5="missing-map",
                score=500_000,
                pp=50.0,
                acc=90.0,
                max_combo=123,
                mods=0,
                n300=250,
                n100=25,
                n50=5,
                nmiss=2,
                ngeki=0,
                nkatu=0,
                grade="B",
                status=2,
                mode=4,
                play_time=datetime(2024, 1, 2),
                time_elapsed=60_000,
                perfect=0,
            ),
            beatmap=None,
        ),
    ]
    assert scores_repo.player_score_calls == [
        {
            "user_id": 3,
            "mode": 4,
            "mods": Mods.HIDDEN.value,
            "strong_mods_equality": True,
            "scope": "best",
            "limit": 50,
            "include_loved": True,
            "include_failed": False,
        },
    ]
    assert beatmap_fetcher.md5s == ["known-map", "missing-map"]


async def test_scores_service_fetches_map_score_listing_rows() -> None:
    service, scores_repo, _ = _service()

    rows = await service.fetch_map_scores(
        map_md5="map-md5",
        mode=GameMode.VANILLA_OSU,
        mods=None,
        strong_mods_equality=False,
        scope="recent",
        limit=25,
    )

    assert rows == [
        MapScoreListingRow(
            id=1,
            map_md5="map-md5",
            score=123,
            pp=12.3,
            acc=98.0,
            max_combo=100,
            mods=0,
            n300=300,
            n100=0,
            n50=0,
            nmiss=0,
            ngeki=0,
            nkatu=0,
            grade="A",
            status=2,
            mode=0,
            play_time=datetime(2024, 1, 1),
            time_elapsed=60_000,
            userid=3,
            perfect=1,
            player_name="player",
            player_country="CA",
            clan_id=None,
            clan_name=None,
            clan_tag=None,
        ),
    ]
    assert scores_repo.map_score_calls == [
        {
            "map_md5": "map-md5",
            "mode": 0,
            "mods": None,
            "strong_mods_equality": False,
            "scope": "recent",
            "limit": 25,
        },
    ]
