from __future__ import annotations

from types import SimpleNamespace

import app.services.replays as replays


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
        schedule_replay_view_increment=scheduled_scores.append,
    )

    result = await service.fetch_replay_file(viewer_id=2, score_id=42)

    assert result == replays.ReplayResult(
        code=replays.ReplayResultCode.FOUND,
        path=replay_path,
    )
    assert scheduled_scores == [score]
