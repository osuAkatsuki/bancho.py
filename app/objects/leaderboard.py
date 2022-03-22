from __future__ import annotations

from typing import Optional
from typing import TypedDict

from app.constants.gamemodes import GameMode
from app.objects.score import Score


class UserScore(TypedDict):
    score: Score
    rank: int


class Leaderboard:
    def __init__(self, mode: GameMode) -> None:
        self.mode = mode
        self.scores: list[Score] = []

    def __len__(self) -> int:
        return len(self.scores)

    def remove_score_index(self, index: int) -> None:
        self.scores.pop(index)

    def find_user_score(self, user_id: int) -> Optional[UserScore]:
        for idx, score in enumerate(self.scores):
            if score.player.id == user_id:
                return {
                    "score": score,
                    "rank": idx + 1,
                }

        return None

    def find_score_rank(self, score_id: int) -> int:
        for idx, score in enumerate(self.scores):
            if score.id == score_id:
                return idx + 1

        return 0

    def remove_user(self, user_id: int) -> None:
        result = self.find_user_score(user_id)

        if result is not None:
            self.remove_score_index(result["rank"] - 1)

    def sort(self) -> None:
        if self.mode > GameMode.VANILLA_MANIA:  # rx/autopilot
            sort = lambda score: score.pp
        else:  # vanilla
            sort = lambda score: score.score

        self.scores = sorted(self.scores, key=sort, reverse=True)

    def add_score(self, score: Score) -> None:
        self.remove_user(score.player.id)

        self.scores.append(score)
        self.sort()
