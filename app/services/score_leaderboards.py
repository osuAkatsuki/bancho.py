from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

from app.constants.leaderboard_types import LeaderboardType
from app.constants.mods import Mods
from app.constants.scoring_metrics import ScoringMetric
from app.objects.player import Player
from app.repositories.scores import BeatmapLeaderboardScoreRow
from app.repositories.scores import PersonalBestLeaderboardScoreRow
from app.repositories.scores import ScoresRepository


class PersonalBestLeaderboardScoreListing(TypedDict):
    id: int
    leaderboard_value: int | float
    max_combo: int
    n50: int
    n100: int
    n300: int
    nmiss: int
    nkatu: int
    ngeki: int
    perfect: int
    mods: int
    time: int
    rank: int


@dataclass(frozen=True)
class LeaderboardScores:
    score_rows: list[BeatmapLeaderboardScoreRow]
    personal_best_score_row: PersonalBestLeaderboardScoreListing | None


@dataclass(frozen=True)
class ScoreLeaderboardsService:
    scores: ScoresRepository

    async def fetch_leaderboard_scores(
        self,
        *,
        leaderboard_type: LeaderboardType | int,
        map_md5: str,
        mode: int,
        mods: Mods,
        player: Player,
        scoring_metric: ScoringMetric,
    ) -> LeaderboardScores:
        mods_filter = mods.value if leaderboard_type == LeaderboardType.Mods else None
        friend_ids = (
            player.friends | {player.id}
            if leaderboard_type == LeaderboardType.Friends
            else None
        )
        country = (
            player.geoloc["country"]["acronym"]
            if leaderboard_type == LeaderboardType.Country
            else None
        )

        score_rows = list(
            await self.scores.fetch_beatmap_leaderboard_scores(
                map_md5=map_md5,
                mode=mode,
                user_id=player.id,
                scoring_metric=scoring_metric,
                mods=mods_filter,
                friend_ids=friend_ids,
                country=country,
            ),
        )

        if not score_rows:
            return LeaderboardScores(
                score_rows=[],
                personal_best_score_row=None,
            )

        personal_best_score_row = (
            await self.scores.fetch_personal_best_leaderboard_score(
                map_md5=map_md5,
                mode=mode,
                user_id=player.id,
                scoring_metric=scoring_metric,
            )
        )

        ranked_personal_best_score_row = None
        if personal_best_score_row is not None:
            rank = await self.scores.fetch_personal_best_leaderboard_rank(
                map_md5=map_md5,
                mode=mode,
                scoring_metric=scoring_metric,
                score=personal_best_score_row["leaderboard_value"],
            )
            ranked_personal_best_score_row = PersonalBestLeaderboardScoreListing(
                **personal_best_score_row,
                rank=rank,
            )

        return LeaderboardScores(
            score_rows=score_rows,
            personal_best_score_row=ranked_personal_best_score_row,
        )
