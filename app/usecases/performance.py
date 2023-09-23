from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TypedDict

from akatsuki_pp_py import Beatmap
from akatsuki_pp_py import Calculator

from app.constants.mods import Mods


@dataclass
class ScoreParams:
    mode: int
    mods: int | None = None
    combo: int | None = None

    # caller may pass either acc OR 300/100/50/geki/katu/miss
    acc: float | None = None

    n300: int | None = None
    n100: int | None = None
    n50: int | None = None
    ngeki: int | None = None
    nkatu: int | None = None
    nmiss: int | None = None


class PerformanceRating(TypedDict):
    pp: float
    pp_acc: float
    pp_aim: float
    pp_speed: float
    pp_flashlight: float
    effective_miss_count: int
    pp_difficulty: float


class DifficultyRating(TypedDict):
    stars: float
    aim: float
    speed: float
    flashlight: float
    slider_factor: float
    speed_note_count: float
    stamina: float
    color: float
    rhythm: float
    peak: float


class PerformanceResult(TypedDict):
    performance: PerformanceRating
    difficulty: DifficultyRating


def calculate_performances(
    osu_file_path: str,
    scores: Iterable[ScoreParams],
) -> list[PerformanceResult]:
    calc_bmap = Beatmap(path=osu_file_path)

    results: list[PerformanceResult] = []

    for score in scores:
        # assert either acc OR 300/100/50/geki/katu/miss is present, but not both
        # if (score.acc is None) == (
        #     score.n300 is None
        #     and score.n100 is None
        #     and score.n50 is None
        #     and score.ngeki is None
        #     and score.nkatu is None
        #     and score.nmiss is None
        # ):
        #     raise ValueError("Either acc OR 300/100/50/geki/katu/miss must be present")

        # rosupp ignores NC and requires DT
        if score.mods is not None:
            if score.mods & Mods.NIGHTCORE:
                score.mods |= Mods.DOUBLETIME

        calculator = Calculator(
            mode=score.mode,
            mods=score.mods or 0,
            combo=score.combo,
            acc=score.acc,
            n300=score.n300,
            n100=score.n100,
            n50=score.n50,
            n_geki=score.ngeki,
            n_katu=score.nkatu,
            n_misses=score.nmiss,
        )
        # TODO: make a fix to akatsuki-pp-py to include python type
        #       definitions for it's public api, so we can remove `type: ignore`
        result = calculator.performance(calc_bmap)

        pp = result.pp  # type: ignore

        if math.isnan(pp) or math.isinf(pp):
            # TODO: report to logserver
            pp = 0.0
        else:
            pp = round(pp, 5)

        results.append(
            {
                "performance": {
                    "pp": pp,
                    "pp_acc": result.pp_acc,  # type: ignore
                    "pp_aim": result.pp_aim,  # type: ignore
                    "pp_speed": result.pp_speed,  # type: ignore
                    "pp_flashlight": result.pp_flashlight,  # type: ignore
                    "effective_miss_count": result.effective_miss_count,  # type: ignore
                    "pp_difficulty": result.pp_difficulty,  # type: ignore
                },
                "difficulty": {
                    "stars": result.difficulty.stars,  # type: ignore
                    "aim": result.difficulty.aim,  # type: ignore
                    "speed": result.difficulty.speed,  # type: ignore
                    "flashlight": result.difficulty.flashlight,  # type: ignore
                    "slider_factor": result.difficulty.slider_factor,  # type: ignore
                    "speed_note_count": result.difficulty.speed_note_count,  # type: ignore
                    "stamina": result.difficulty.stamina,  # type: ignore
                    "color": result.difficulty.color,  # type: ignore
                    "rhythm": result.difficulty.rhythm,  # type: ignore
                    "peak": result.difficulty.peak,  # type: ignore
                },
            },
        )

    return results
