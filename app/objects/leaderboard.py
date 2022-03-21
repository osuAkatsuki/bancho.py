from __future__ import annotations

import asyncio
from typing import Optional
from typing import TYPE_CHECKING
from typing import TypedDict

import app.state
from app.constants.gamemodes import GameMode
from app.objects.score import Score

if TYPE_CHECKING:
    from app.objects.beatmap import Beatmap


class UserScore(TypedDict):
    score: Score
    rank: int


class Leaderboard:
    def __init__(self, mode: GameMode) -> None:
        self.mode = mode
        self.scores: list[Score] = []

    def __len__(self) -> int:
        return len(self.scores)

    @classmethod
    async def create_leaderboard(
        cls, mode: GameMode, beatmap: "Beatmap",
    ) -> Leaderboard:
        """Create a leaderboard object with populated scores."""

        leaderboard = Leaderboard(mode)

        rows = await app.state.services.database.fetch_all(
            "SELECT id, map_md5, userid, pp, score, "
            "max_combo, mods, acc, n300, n100, n50, "
            "nmiss, ngeki, nkatu, grade, perfect, "
            "status, mode, play_time, "
            "time_elapsed, client_flags, online_checksum "
            "FROM scores WHERE map_md5 = :map_md5 AND status = 2 "
            "AND mode = :mode",
            {"map_md5": beatmap.md5, "mode": mode.value},
        )

        for row in rows:
            score_obj = Score.from_row(row, calculate_rank=False)
            leaderboard.scores.append(score_obj)

        await leaderboard.sort()
        return leaderboard

    async def remove_score_index(self, index: int) -> None:
        self.scores.pop(index)

    async def find_user_score(self, user_id: int) -> Optional[UserScore]:
        for idx, score in enumerate(self.scores):
            if score.player.id == user_id:
                return {
                    "score": score,
                    "rank": idx + 1,
                }

        return None

    async def find_score_rank(self, score_id: int) -> int:
        for idx, score in enumerate(self.scores):
            if score.id == score_id:
                return idx + 1

        return 0

    async def remove_user(self, user_id: int) -> None:
        result = await self.find_user_score(user_id)

        if result is not None:
            self.remove_score_index(result["rank"] - 1)

    async def sort(self) -> None:
        if self.mode > GameMode.VANILLA_MANIA:  # rx/autopilot
            sort = lambda score: score.pp
        else:  # vanilla
            sort = lambda score: score.score

        self.scores = sorted(self.scores, key=sort, reverse=True)

    async def add_score(self, score: Score) -> None:
        await self.remove_user(score.player.id)

        self.scores.append(score)
        await self.sort()
