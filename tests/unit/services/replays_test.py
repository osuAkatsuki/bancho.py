from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import app.services.replays as replays
from app.repositories.scores import ReplayHeader


def _replay_header(**overrides: object) -> ReplayHeader:
    defaults: dict[str, object] = {
        "username": "cmyui",
        "map_md5": "a" * 32,
        "artist": "xi",
        "title": "FREEDOM DiVE",
        "version": "FOUR DIMENSIONS",
        "mode": 0,
        "n300": 1961,
        "n100": 5,
        "n50": 0,
        "ngeki": 247,
        "nkatu": 4,
        "nmiss": 0,
        "score": 132408001,
        "max_combo": 2385,
        "perfect": 1,
        "mods": 72,
        "play_time": datetime(2024, 1, 1, 12, 30, 0),
    }
    defaults.update(overrides)
    return ReplayHeader(**defaults)  # type: ignore[arg-type]


class _FakeReplayHeaderFetcher:
    def __init__(self, header: ReplayHeader | None) -> None:
        self.header = header

    async def __call__(self, score_id: int) -> ReplayHeader | None:
        return self.header


class _FakeScoreFetcher:
    def __init__(self, score: object | None) -> None:
        self.score = score
        self.score_ids: list[int] = []

    async def __call__(self, score_id: int) -> object | None:
        self.score_ids.append(score_id)
        return self.score


async def test_replay_service_returns_not_found_when_score_does_not_exist(
    tmp_path,
) -> None:
    fetch_score = _FakeScoreFetcher(score=None)
    scheduled_scores: list[object] = []
    service = replays.ReplayService(
        replays_path=tmp_path,
        fetch_score=fetch_score,
        fetch_replay_header=_FakeReplayHeaderFetcher(None),
        schedule_replay_view_increment=scheduled_scores.append,
    )

    result = await service.fetch_replay_file(viewer_id=1, score_id=42)

    assert result.code is replays.ReplayResultCode.NOT_FOUND
    assert fetch_score.score_ids == [42]
    assert scheduled_scores == []


async def test_replay_service_schedules_view_increment_for_other_player(
    tmp_path,
) -> None:
    score = SimpleNamespace(player=SimpleNamespace(id=1))
    fetch_score = _FakeScoreFetcher(score=score)
    scheduled_scores: list[object] = []
    replay_path = tmp_path / "42.osr"
    replay_path.write_bytes(b"replay")
    service = replays.ReplayService(
        replays_path=tmp_path,
        fetch_score=fetch_score,
        fetch_replay_header=_FakeReplayHeaderFetcher(None),
        schedule_replay_view_increment=scheduled_scores.append,
    )

    result = await service.fetch_replay_file(viewer_id=2, score_id=42)

    assert result == replays.ReplayResult(
        code=replays.ReplayResultCode.FOUND,
        path=replay_path,
    )
    assert scheduled_scores == [score]


async def test_replay_service_builds_a_full_replay(tmp_path) -> None:
    (tmp_path / "42.osr").write_bytes(b"raw replay frames")
    service = replays.ReplayService(
        replays_path=tmp_path,
        fetch_score=_FakeScoreFetcher(None),
        fetch_replay_header=_FakeReplayHeaderFetcher(_replay_header()),
        schedule_replay_view_increment=lambda score: None,
    )

    replay = await service.build_full_replay(42)

    assert replay is not None
    assert b"raw replay frames" in replay.data
    assert b"cmyui" in replay.data
    assert replay.filename == (
        "cmyui - xi - FREEDOM DiVE [FOUR DIMENSIONS] (2024-01-01).osr"
    )


async def test_replay_service_full_replay_requires_the_file(tmp_path) -> None:
    service = replays.ReplayService(
        replays_path=tmp_path,
        fetch_score=_FakeScoreFetcher(None),
        fetch_replay_header=_FakeReplayHeaderFetcher(_replay_header()),
        schedule_replay_view_increment=lambda score: None,
    )

    assert await service.build_full_replay(42) is None


async def test_replay_service_full_replay_requires_the_score_row(tmp_path) -> None:
    (tmp_path / "42.osr").write_bytes(b"raw replay frames")
    service = replays.ReplayService(
        replays_path=tmp_path,
        fetch_score=_FakeScoreFetcher(None),
        fetch_replay_header=_FakeReplayHeaderFetcher(None),
        schedule_replay_view_increment=lambda score: None,
    )

    assert await service.build_full_replay(42) is None
