from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from app.objects.score import Score


class ScoreFetcher(Protocol):
    def __call__(self, score_id: int) -> Awaitable[Score | None]: ...


class ReplayViewScheduler(Protocol):
    def __call__(self, score: Score) -> None: ...


class ReplayResultCode(StrEnum):
    FOUND = "found"
    NOT_FOUND = "not_found"


@dataclass(frozen=True)
class ReplayResult:
    code: ReplayResultCode
    path: Path | None = None


@dataclass(frozen=True)
class ReplayService:
    replays_path: Path
    fetch_score: ScoreFetcher
    schedule_replay_view_increment: ReplayViewScheduler

    async def fetch_replay_file(
        self,
        *,
        viewer_id: int,
        score_id: int,
    ) -> ReplayResult:
        score = await self.fetch_score(score_id)
        if score is None:
            return ReplayResult(code=ReplayResultCode.NOT_FOUND)

        replay_path = self.replays_path / f"{score_id}.osr"
        if not replay_path.exists():
            return ReplayResult(code=ReplayResultCode.NOT_FOUND)

        player = getattr(score, "player", None)
        if player is not None and viewer_id != player.id:
            self.schedule_replay_view_increment(score)

        return ReplayResult(code=ReplayResultCode.FOUND, path=replay_path)
