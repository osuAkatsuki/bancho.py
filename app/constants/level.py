from __future__ import annotations

import math


# NOTE: https://osu.ppy.sh/wiki/en/Gameplay/Score/Total_score
def get_required_score_for_level(level: int) -> int:
    if level <= 1:
        return 0

    if level <= 100:
        return math.ceil(
            (5000 / 3) * (4 * level**3 - 3 * level**2 - level)
            + 1.25 * 1.8 ** (level - 60),
        )
    else:
        return math.ceil(26931190827 + 99999999999 * (level - 100) + 2)


def get_level(score: int) -> int:
    if score <= 0:
        return 1

    if score >= get_required_score_for_level(99):
        return 100 + int((score - get_required_score_for_level(99)) / 100000000000)

    levels = [get_required_score_for_level(level) for level in range(1, 101)]

    for level, level_score in enumerate(levels, start=1):
        if score <= level_score:
            return level

    return 1


def get_level_precise(score: int) -> float:
    baseLevel = get_level(score)
    baseLevelScore = get_required_score_for_level(baseLevel)
    scoreProgress = score - baseLevelScore
    scoreLevelDifference = get_required_score_for_level(baseLevel + 1) - baseLevelScore

    res = float(scoreProgress) / float(scoreLevelDifference) + float(baseLevel)
    if math.isinf(res) or math.isnan(res):
        return 0

    return res
