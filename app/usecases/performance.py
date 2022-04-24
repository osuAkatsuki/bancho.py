from __future__ import annotations

import math
import subprocess
from typing import Optional
from typing import TypedDict

import orjson

from app.constants.mods import mod2modstr_dict
from app.constants.mods import Mods
from app.logging import Ansi
from app.logging import log
from app.utils import OSU_TOOLS_EXEC_PATH


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


def mods2modlist(mods: int) -> list[str]:
    if mods == Mods.NOMOD:
        return []

    result = []
    _dict = mod2modstr_dict

    for mod in Mods:
        if mods & mod:
            result.append(_dict[mod])

    return result


def calculate_performances_std(
    osu_file_path: str,
    scores: list[StdTaikoCatchScore],
) -> list[DifficultyRating]:
    results: list[DifficultyRating] = []

    for score in scores:
        cmd = [OSU_TOOLS_EXEC_PATH, "simulate", "osu", "-j"]

        if score["mods"] is not None:
            modlist = mods2modlist(score["mods"])
            for mod in modlist:
                cmd.append("-m")
                cmd.append(mod)

        if score["nmiss"] is not None:
            cmd.append("-X")
            cmd.append(str(score["nmiss"]))

        if score["combo"] is not None:
            cmd.append("-c")
            cmd.append(str(score["combo"]))

        if score["acc"] is not None:
            cmd.append("-a")
            cmd.append(str(score["acc"]))

        cmd.append(osu_file_path)

        log(f"Running {cmd}", Ansi.LMAGENTA)

        p = subprocess.Popen(
            args=cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if exit_code := p.wait():
            _, stderr = p.communicate()
            print(stderr.decode())
            log(
                f"Failed to calculate performance points for map {osu_file_path}",
                Ansi.LRED,
            )
            raise Exception()

        stdout, _ = p.communicate()
        obj = orjson.loads(stdout.decode())

        pp = obj["performance_attributes"]["pp"]
        sr = obj["difficulty_attributes"]["star_rating"]

        if math.isnan(pp) or math.isinf(pp):
            # TODO: report to logserver
            pp = 0.0
            sr = 0.0

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

    for score in scores:
        cmd = [OSU_TOOLS_EXEC_PATH, "simulate", "taiko", "-j"]

        if score["mods"] is not None:
            modlist = mods2modlist(score["mods"])
            for mod in modlist:
                cmd.append("-m")
                cmd.append(mod)

        if score["nmiss"] is not None:
            cmd.append("-X")
            cmd.append(str(score["nmiss"]))

        if score["combo"] is not None:
            cmd.append("-c")
            cmd.append(str(score["combo"]))

        if score["acc"] is not None:
            cmd.append("-a")
            cmd.append(str(score["acc"]))

        cmd.append(osu_file_path)

        p = subprocess.Popen(
            args=cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if exit_code := p.wait():
            _, stderr = p.communicate()
            print(stderr.decode())
            log(
                f"Failed to calculate performance points for map {osu_file_path}",
                Ansi.LRED,
            )
            raise Exception()

        stdout, _ = p.communicate()
        obj = orjson.loads(stdout.decode())

        pp = obj["performance_attributes"]["pp"]
        sr = obj["difficulty_attributes"]["star_rating"]

        if math.isnan(pp) or math.isinf(pp):
            # TODO: report to logserver
            pp = 0.0
            sr = 0.0

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

    for score in scores:
        cmd = [OSU_TOOLS_EXEC_PATH, "simulate", "catch", "-j"]

        if score["mods"] is not None:
            modlist = mods2modlist(score["mods"])
            for mod in modlist:
                cmd.append("-m")
                cmd.append(mod)

        if score["nmiss"] is not None:
            cmd.append("-X")
            cmd.append(str(score["nmiss"]))

        if score["combo"] is not None:
            cmd.append("-c")
            cmd.append(str(score["combo"]))

        if score["acc"] is not None:
            cmd.append("-a")
            cmd.append(str(score["acc"]))

        cmd.append(osu_file_path)

        p = subprocess.Popen(
            args=cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if exit_code := p.wait():
            _, stderr = p.communicate()
            print(stderr.decode())
            log(
                f"Failed to calculate performance points for map {osu_file_path}",
                Ansi.LRED,
            )
            raise Exception()

        stdout, _ = p.communicate()
        obj = orjson.loads(stdout.decode())

        pp = obj["performance_attributes"]["pp"]
        sr = obj["difficulty_attributes"]["star_rating"]

        if math.isnan(pp) or math.isinf(pp):
            # TODO: report to logserver
            pp = 0.0
            sr = 0.0

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

    for score in scores:
        cmd = [OSU_TOOLS_EXEC_PATH, "simulate", "mania", "-j"]

        if score["mods"] is not None:
            modlist = mods2modlist(score["mods"])
            for mod in modlist:
                cmd.append("-m")
                cmd.append(mod)

        if score["score"] is not None:
            cmd.append("-s")
            cmd.append(str(score["score"]))

        cmd.append(osu_file_path)

        p = subprocess.Popen(
            args=cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if exit_code := p.wait():
            _, stderr = p.communicate()
            print(stderr.decode())
            log(
                f"Failed to calculate performance points for map {osu_file_path}",
                Ansi.LRED,
            )
            raise Exception()

        stdout, _ = p.communicate()
        obj = orjson.loads(stdout.decode())

        pp = obj["performance_attributes"]["pp"]
        sr = obj["difficulty_attributes"]["star_rating"]

        if math.isnan(pp) or math.isinf(pp):
            # TODO: report to logserver
            pp = 0.0
            sr = 0.0

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
    score: int


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
                "score": score.get("score"),
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
