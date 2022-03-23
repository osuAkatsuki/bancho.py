from __future__ import annotations

from pathlib import Path

import app.usecases.performance
from app.objects.score import Score
from app.usecases.performance import ScoreDifficultyParams


def calculate_performance(score: Score, osu_file_path: Path) -> tuple[float, float]:
    """Calculate PP and star rating for our score."""
    mode_vn = score.mode.as_vanilla

    if mode_vn in (0, 1, 2):
        score_args: ScoreDifficultyParams = {
            "acc": score.acc,
            "combo": score.max_combo,
            "nmiss": score.nmiss,
        }
    else:  # mode_vn == 3
        score_args: ScoreDifficultyParams = {
            "score": score.score,
        }

    result = app.usecases.performance.calculate_performances(
        osu_file_path=str(osu_file_path),
        mode=mode_vn,
        mods=int(score.mods),
        scores=[score_args],
    )

    return result[0]["performance"], result[0]["star_rating"]
