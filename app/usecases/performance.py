from __future__ import annotations

import math
from typing import Optional
from typing import TypedDict

from rosu_pp_py import Beatmap
from rosu_pp_py import Calculator


class DifficultyRating(TypedDict):
    performance: float
    star_rating: float


class StdTaikoCatchScore(TypedDict):
    mods: Optional[int]
    acc: Optional[float]
    combo: Optional[int]
    nmiss: Optional[int]


class ManiaScore(TypedDict):
    mods: Optional[int]
    score: Optional[int]


def calculate_performances_std(
    osu_file_path: str,
    scores: list[StdTaikoCatchScore],
) -> list[DifficultyRating]:
    results: list[DifficultyRating] = []

    calc_bmap = Beatmap(path=osu_file_path)
    for score in scores:
        mods = score["mods"] if score["mods"] != None else 0
        acc = score["acc"] if score["acc"] != None else 100.00
        nmisses = score["nmiss"] if score["nmiss"] != None else 0
        combo = score["combo"]

        calculator = Calculator(mods=mods)
        calculator.set_acc(acc)
        calculator.set_n_misses(nmisses)
        if combo != None:
            calculator.set_combo(combo)

        result = calculator.performance(calc_bmap)

        pp = result.pp
        sr = result.difficulty.stars

        if math.isnan(pp) or math.isinf(pp):
            # TODO: report to logserver
            pp = 0.0
            sr = 0.0
        else:
            pp = round(pp, 5)

        results.append(
            {
                "performance": pp,
                "star_rating": sr,
            },
        )

    return results


def calculate_performances_taiko(
    osu_file_path: str,
    scores: list[StdTaikoCatchScore],
) -> list[DifficultyRating]:
    results: list[DifficultyRating] = []

    calc_bmap = Beatmap(path=osu_file_path)
    for score in scores:
        mods = score["mods"] if score["mods"] != None else 0
        acc = score["acc"] if score["acc"] != None else 100.00
        nmisses = score["nmiss"] if score["nmiss"] != None else 0
        combo = score["combo"]

        calculator = Calculator(mods=mods, mode=1)
        calculator.set_acc(acc)
        calculator.set_n_misses(nmisses)
        if combo != None:
            calculator.set_combo(combo)

        result = calculator.performance(calc_bmap)

        pp = result.pp
        sr = result.difficulty.stars

        if math.isnan(pp) or math.isinf(pp):
            # TODO: report to logserver
            pp = 0.0
            sr = 0.0
        else:
            pp = round(pp, 5)

        results.append(
            {
                "performance": pp,
                "star_rating": sr,
            },
        )

    return results


def calculate_performances_catch(
    osu_file_path: str,
    scores: list[StdTaikoCatchScore],
) -> list[DifficultyRating]:
    results: list[DifficultyRating] = []

    calc_bmap = Beatmap(path=osu_file_path)
    for score in scores:
        mods = score["mods"] if score["mods"] != None else 0
        acc = score["acc"] if score["acc"] != None else 100.00
        nmisses = score["nmiss"] if score["nmiss"] != None else 0
        combo = score["combo"]

        calculator = Calculator(mods=mods, mode=2)
        calculator.set_acc(acc)
        calculator.set_n_misses(nmisses)
        if combo != None:
            calculator.set_combo(combo)

        result = calculator.performance(calc_bmap)

        pp = result.pp
        sr = result.difficulty.stars

        if math.isnan(pp) or math.isinf(pp):
            # TODO: report to logserver
            pp = 0.0
            sr = 0.0
        else:
            pp = round(pp, 5)

        results.append(
            {
                "performance": pp,
                "star_rating": sr,
            },
        )

    return results


def calculate_performances_mania(
    osu_file_path: str,
    scores: list[ManiaScore],
) -> list[DifficultyRating]:
    results: list[DifficultyRating] = []

    calc_bmap = Beatmap(path=osu_file_path)
    for score in scores:
        mods = score["mods"] if score["mods"] != None else 0
        acc = score["acc"]

        calculator = Calculator(mods=mods, mode=3)
        if acc != None:
            calculator.set_acc(acc)
        else:
            calculator.set_n_geki(score["n320"])
            calculator.set_n300(score["n300"])
            calculator.set_n_katu(score["n200"])
            calculator.set_n100(score["n100"])
            calculator.set_n50(score["n50"])
            calculator.set_n_misses(score["nmiss"])

        result = calculator.performance(calc_bmap)

        pp = result.pp
        sr = result.difficulty.stars

        if math.isnan(pp) or math.isinf(pp):
            # TODO: report to logserver
            pp = 0.0
            sr = 0.0
        else:
            pp = round(pp, 5)

        results.append(
            {
                "performance": pp,
                "star_rating": sr,
            },
        )

    return results


class ScoreDifficultyParams(TypedDict, total=False):
    # std, taiko, catch
    acc: float
    combo: int
    nmiss: int

    # mania
    acc: float
    n320: int
    n300: int
    n200: int
    n100: int
    n50: int
    nmiss: int


def calculate_performances(
    osu_file_path: str,
    mode: int,
    mods: Optional[int],
    scores: list[ScoreDifficultyParams],
) -> list[DifficultyRating]:
    if mode in (0, 1, 2):
        std_taiko_catch_scores: list[StdTaikoCatchScore] = [
            {
                "mods": mods,
                "acc": score.get("acc"),
                "combo": score.get("combo"),
                "nmiss": score.get("nmiss"),
            }
            for score in scores
        ]

        if mode == 0:
            results = calculate_performances_std(
                osu_file_path=osu_file_path,
                scores=std_taiko_catch_scores,
            )
        elif mode == 1:
            results = calculate_performances_taiko(
                osu_file_path=osu_file_path,
                scores=std_taiko_catch_scores,
            )
        elif mode == 2:
            results = calculate_performances_catch(
                osu_file_path=osu_file_path,
                scores=std_taiko_catch_scores,
            )

    elif mode == 3:
        mania_scores: list[ManiaScore] = [
            {
                "mods": mods,
                "acc": score.get("acc"),
                "n320": score.get("n320"),
                "n300": score.get("n300"),
                "n200": score.get("n200"),
                "n100": score.get("n100"),
                "n50": score.get("n50"),
                "nmiss": score.get("nmiss"),
            }
            for score in scores
        ]

        results = calculate_performances_mania(
            osu_file_path=osu_file_path,
            scores=mania_scores,
        )
    else:
        raise NotImplementedError

    return results
