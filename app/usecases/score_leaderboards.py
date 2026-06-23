from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from typing import Protocol

from app.constants.leaderboard_types import LeaderboardType
from app.constants.mods import Mods
from app.constants.scoring_metrics import ScoringMetric
from app.objects.player import Player

LeaderboardScore = dict[str, Any]


class ScoresRepository(Protocol):
    async def fetch_beatmap_leaderboard_scores(
        self,
        *,
        map_md5: str,
        mode: int,
        user_id: int,
        scoring_metric: ScoringMetric,
        mods: int | None = None,
        friend_ids: set[int] | None = None,
        country: str | None = None,
        limit: int = 50,
    ) -> Sequence[LeaderboardScore]: ...

    async def fetch_personal_best_leaderboard_score(
        self,
        *,
        map_md5: str,
        mode: int,
        user_id: int,
        scoring_metric: ScoringMetric,
    ) -> LeaderboardScore | None: ...

    async def fetch_personal_best_leaderboard_rank(
        self,
        *,
        map_md5: str,
        mode: int,
        scoring_metric: ScoringMetric,
        score: int | float,
    ) -> int: ...


@dataclass(frozen=True)
class LeaderboardScores:
    score_rows: list[LeaderboardScore]
    personal_best_score_row: LeaderboardScore | None


async def fetch_leaderboard_scores(
    *,
    leaderboard_type: LeaderboardType | int,
    map_md5: str,
    mode: int,
    mods: Mods,
    player: Player,
    scoring_metric: ScoringMetric,
    scores: ScoresRepository,
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
        await scores.fetch_beatmap_leaderboard_scores(
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

    personal_best_score_row = await scores.fetch_personal_best_leaderboard_score(
        map_md5=map_md5,
        mode=mode,
        user_id=player.id,
        scoring_metric=scoring_metric,
    )

    if personal_best_score_row is not None:
        personal_best_score_row["rank"] = (
            await scores.fetch_personal_best_leaderboard_rank(
                map_md5=map_md5,
                mode=mode,
                scoring_metric=scoring_metric,
                score=personal_best_score_row["_score"],
            )
        )

    return LeaderboardScores(
        score_rows=score_rows,
        personal_best_score_row=personal_best_score_row,
    )
