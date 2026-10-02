from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.constants.clientflags import ClientFlags
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.constants.score_statuses import SubmissionStatus
from app.objects.score import Grade
from app.objects.score import Score as DomainScore
from app.repositories.scores import Score as StoredScore
from app.services.scores import ScoreDomainService


def _stored_score(
    *,
    id: int = 42,
    pp: float = 123.45,
    score: int = 1_000_000,
    mode: int = GameMode.RELAX_OSU.value,
) -> StoredScore:
    return StoredScore(
        id=id,
        map_md5="map-md5",
        score=score,
        pp=pp,
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
        status=SubmissionStatus.BEST.value,
        mode=mode,
        play_time=datetime(2024, 1, 1),
        time_elapsed=60_000,
        client_flags=ClientFlags.CHECKSUM_FAILURE.value,
        userid=7,
        perfect=1,
        online_checksum="checksum",
    )


def _domain_score(
    *,
    mode: GameMode = GameMode.RELAX_OSU,
    pp: float = 150.0,
    score_value: int = 900_000,
) -> DomainScore:
    score = DomainScore()
    score.bmap = SimpleNamespace(id=10, md5="map-md5")
    score.player = SimpleNamespace(id=7)
    score.mode = mode
    score.mods = Mods.HIDDEN
    score.pp = pp
    score.score = score_value
    score.max_combo = 321
    score.n300 = 300
    score.n100 = 5
    score.n50 = 1
    score.nmiss = 0
    score.ngeki = 0
    score.nkatu = 0
    score.status = SubmissionStatus.SUBMITTED
    score.prev_best = None
    return score


class _FakeScoresRepository:
    def __init__(
        self,
        *,
        stored_scores: dict[int, StoredScore] | None = None,
        previous_scores: list[StoredScore] | None = None,
        placement: int = 1,
    ) -> None:
        self.stored_scores = stored_scores or {}
        self.previous_scores = previous_scores or []
        self.placement = placement
        self.fetch_one_calls: list[int] = []
        self.fetch_many_calls: list[dict[str, object]] = []
        self.placement_calls: list[dict[str, object]] = []

    async def fetch_one(self, id: int) -> StoredScore | None:
        self.fetch_one_calls.append(id)
        return self.stored_scores.get(id)

    async def fetch_many(self, **filters: object) -> list[StoredScore]:
        self.fetch_many_calls.append(filters)
        return self.previous_scores

    async def fetch_personal_best_leaderboard_rank(
        self,
        **params: object,
    ) -> int:
        self.placement_calls.append(params)
        return self.placement


class _FakeStatsRepository:
    def __init__(self) -> None:
        self.replay_view_calls: list[tuple[int, int]] = []

    async def increment_replay_views(self, player_id: int, mode: int) -> None:
        self.replay_view_calls.append((player_id, mode))


class _FakePerformanceService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[object]]] = []

    def calculate_performances(
        self,
        osu_file_path: str,
        scores: list[object],
    ) -> list[object]:
        self.calls.append((osu_file_path, scores))
        return [
            SimpleNamespace(
                performance=SimpleNamespace(pp=321.123),
                difficulty=SimpleNamespace(stars=6.75),
            ),
        ]


def _service(
    *,
    scores: _FakeScoresRepository | None = None,
    stats: _FakeStatsRepository | None = None,
    performance: _FakePerformanceService | None = None,
    beatmap: object | None = None,
    player: object | None = None,
    beatmaps_path: Path = Path("/beatmaps"),
) -> tuple[
    ScoreDomainService,
    list[str],
    list[int],
]:
    beatmap_calls: list[str] = []
    player_calls: list[int] = []

    async def fetch_beatmap(md5: str, set_id: int = -1) -> object | None:
        beatmap_calls.append(md5)
        return beatmap

    async def fetch_player(player_id: int) -> object | None:
        player_calls.append(player_id)
        return player

    return (
        ScoreDomainService(
            scores=scores or _FakeScoresRepository(),  # type: ignore[arg-type]
            stats=stats or _FakeStatsRepository(),  # type: ignore[arg-type]
            fetch_beatmap=fetch_beatmap,  # type: ignore[arg-type]
            fetch_player=fetch_player,  # type: ignore[arg-type]
            performance=performance or _FakePerformanceService(),  # type: ignore[arg-type]
            beatmaps_path=beatmaps_path,
        ),
        beatmap_calls,
        player_calls,
    )


async def test_fetch_returns_none_without_hydrating_missing_score() -> None:
    scores = _FakeScoresRepository()
    service, beatmap_calls, player_calls = _service(scores=scores)

    assert await service.fetch(404) is None
    assert scores.fetch_one_calls == [404]
    assert beatmap_calls == []
    assert player_calls == []


async def test_fetch_hydrates_score_and_calculates_placement() -> None:
    stored = _stored_score()
    scores = _FakeScoresRepository(stored_scores={stored.id: stored}, placement=3)
    beatmap = SimpleNamespace(md5=stored.map_md5)
    player = SimpleNamespace(id=stored.userid)
    service, beatmap_calls, player_calls = _service(
        scores=scores,
        beatmap=beatmap,
        player=player,
    )

    score = await service.fetch(stored.id)

    assert score is not None
    assert score.id == stored.id
    assert score.bmap is beatmap
    assert score.player is player
    assert score.sr == 0.0
    assert score.pp == stored.pp
    assert score.score == stored.score
    assert score.mods is Mods.HIDDEN
    assert score.grade is Grade.A
    assert score.status is SubmissionStatus.BEST
    assert score.passed is True
    assert score.mode is GameMode.RELAX_OSU
    assert score.client_flags == ClientFlags.CHECKSUM_FAILURE
    assert score.rank == 3
    assert beatmap_calls == [stored.map_md5]
    assert player_calls == [stored.userid]


@pytest.mark.parametrize(
    ("mode", "expected_metric", "expected_value"),
    [
        (GameMode.VANILLA_OSU, "score", 900_000),
        (GameMode.RELAX_OSU, "pp", 150.0),
    ],
)
async def test_calculate_placement_uses_mode_scoring_metric(
    mode: GameMode,
    expected_metric: str,
    expected_value: int | float,
) -> None:
    scores = _FakeScoresRepository(placement=4)
    service, _, _ = _service(scores=scores)
    score = _domain_score(mode=mode)

    assert await service.calculate_placement(score) == 4
    assert scores.placement_calls == [
        {
            "map_md5": "map-md5",
            "mode": mode.value,
            "scoring_metric": expected_metric,
            "score": expected_value,
        },
    ]


async def test_calculate_submission_status_marks_first_score_best() -> None:
    scores = _FakeScoresRepository()
    service, _, _ = _service(scores=scores)
    score = _domain_score()

    await service.calculate_submission_status(score)

    assert score.status is SubmissionStatus.BEST
    assert score.prev_best is None
    assert scores.fetch_many_calls == [
        {
            "user_id": 7,
            "map_md5": "map-md5",
            "mode": GameMode.RELAX_OSU.value,
            "status": SubmissionStatus.BEST.value,
            "include_hidden_players": True,
        },
    ]


async def test_calculate_submission_status_demotes_previous_best() -> None:
    previous = _stored_score(id=12, pp=100.0)
    scores = _FakeScoresRepository(
        stored_scores={previous.id: previous},
        previous_scores=[previous],
    )
    previous_beatmap = SimpleNamespace(md5=previous.map_md5)
    service, _, _ = _service(
        scores=scores,
        beatmap=previous_beatmap,
        player=SimpleNamespace(id=previous.userid),
    )
    score = _domain_score(pp=150.0)

    await service.calculate_submission_status(score)

    assert score.status is SubmissionStatus.BEST
    assert score.prev_best is not None
    assert score.prev_best.id == previous.id
    assert score.prev_best.status is SubmissionStatus.SUBMITTED


async def test_calculate_submission_status_keeps_worse_score_submitted() -> None:
    previous = _stored_score(id=12, pp=200.0)
    scores = _FakeScoresRepository(
        stored_scores={previous.id: previous},
        previous_scores=[previous],
    )
    service, _, _ = _service(
        scores=scores,
        beatmap=SimpleNamespace(md5=previous.map_md5),
        player=SimpleNamespace(id=previous.userid),
    )
    score = _domain_score(pp=150.0)

    await service.calculate_submission_status(score)

    assert score.status is SubmissionStatus.SUBMITTED
    assert score.prev_best is not None
    assert score.prev_best.status is SubmissionStatus.BEST


def test_calculate_performance_uses_injected_service_and_path() -> None:
    performance = _FakePerformanceService()
    service, _, _ = _service(
        performance=performance,
        beatmaps_path=Path("/test-beatmaps"),
    )
    score = _domain_score()

    assert service.calculate_performance(score, 315) == (321.123, 6.75)
    assert performance.calls[0][0] == "/test-beatmaps/315.osu"
    [params] = performance.calls[0][1]
    assert params.mode == GameMode.VANILLA_OSU.value
    assert params.mods == Mods.HIDDEN.value
    assert params.combo == 321
    assert params.n300 == 300
    assert params.nmiss == 0


async def test_increment_replay_views_uses_stats_repository() -> None:
    stats = _FakeStatsRepository()
    service, _, _ = _service(stats=stats)
    score = _domain_score(mode=GameMode.RELAX_OSU)

    await service.increment_replay_views(score)

    assert stats.replay_view_calls == [(7, GameMode.RELAX_OSU.value)]
