from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable
from typing import Optional
from typing import TypedDict

from akatsuki_pp_py import Beatmap
from akatsuki_pp_py import Calculator


@dataclass
class ScoreParams:
    mode: int
    mods: Optional[int] = None
    combo: Optional[int] = None

    # caller may pass either acc OR 300/100/50/geki/katu/miss
    acc: Optional[float] = None

    n300: Optional[int] = None
    n100: Optional[int] = None
    n50: Optional[int] = None
    ngeki: Optional[int] = None
    nkatu: Optional[int] = None
    nmiss: Optional[int] = None


class DifficultyRating(TypedDict):
    performance: float
    star_rating: float


def calculate_performances(
    osu_file_path: str,
    scores: Iterable[ScoreParams],
) -> list[DifficultyRating]:
    calc_bmap = Beatmap(path=osu_file_path)

    results: list[DifficultyRating] = []

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

        calculator = Calculator(
            mode=score.mode,
            mods=score.mods if score.mods is not None else 0,
            combo=score.combo,
            acc=score.acc,
            n300=score.n300,
            n100=score.n100,
            n50=score.n50,
            n_geki=score.ngeki,
            n_katu=score.nkatu,
            n_misses=score.nmiss,
        )
        result = calculator.performance(calc_bmap)

        pp = result.pp
        sr = result.difficulty.stars

        if math.isnan(pp) or math.isinf(pp):
            # TODO: report to logserver
            pp = 0.0
            sr = 0.0
        else:
            pp = round(pp, 5)

        results.append({"performance": pp, "star_rating": sr})

    return results
