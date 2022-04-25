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
    
class ScoreDifficultyParams(TypedDict, total=False):
    # std, taiko, catch
    combo: int
    n100: int
    n50: int
    nmiss: int
    acc: float

    # mania
    score: int

def mods2modlist(mods: int) -> list[str]:
    if mods == Mods.NOMOD:
        return []

    result = []
    _dict = mod2modstr_dict

    for mod in Mods:
        if mods & mod:
            result.append(_dict[mod])

    return result


def calculate_performances_stc(
    mode: int,
    mods: Optional[int],
    osu_file_path: str,
    scores: list[ScoreDifficultyParams],
) -> list[DifficultyRating]:
    results: list[DifficultyRating] = []
    
    if mode in (0, 4, 8):
        mode_str = 'std'
    elif mode in (1, 5):
        mode_str = 'taiko'
    elif mode in (2, 6):
        mode_str = 'catch'

    for score in scores:
        cmd = [OSU_TOOLS_EXEC_PATH, "simulate", mode_str, "-j"]

        if mods is not None:
            modlist = mods2modlist(mods)
            for mod in modlist:
                cmd.append("-m")
                cmd.append(mod)

        if score.get("nmiss") is not None:
            cmd.append("-X")
            cmd.append(str(score.get("nmiss")))

        if score.get("combo") is not None:
            cmd.append("-c")
            cmd.append(str(score.get("combo")))

        if score.get("acc") is not None:
            cmd.append("-a")
            cmd.append(str(score.get("acc")))
        else:
            if score.get("n100") is not None:
                cmd.append("-G")
                cmd.append(str(score.get("n100")))

            if score.get("n50") is not None:
                cmd.append("-M")
                cmd.append(str(score.get("n50")))

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
        
        if mode == 4:
            pp = obj["performance_attributes"]["aim"]
        elif mode == 8:
            pp = obj["performance_attributes"]["speed"]
        else:
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
    mods: Optional[int],
    scores: list[ScoreDifficultyParams],
) -> list[DifficultyRating]:
    results: list[DifficultyRating] = []

    for score in scores:
        cmd = [OSU_TOOLS_EXEC_PATH, "simulate", "mania", "-j"]

        if mods is not None:
            modlist = mods2modlist(mods)
            for mod in modlist:
                cmd.append("-m")
                cmd.append(mod)

        if score.get("score") is not None:
            cmd.append("-s")
            cmd.append(str(score.get("score")))

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


def calculate_performances(
    osu_file_path: str,
    mode: int,
    mods: Optional[int],
    scores: list[ScoreDifficultyParams],
) -> list[DifficultyRating]:
    if mode in (0, 1, 2, 4, 5, 6, 8):
        results = calculate_performances_stc(
            mode,
            mods,
            osu_file_path,
            scores,
        )

    elif mode == 3:
        results = calculate_performances_mania(
            mods,
            osu_file_path,
            scores,
        )
    else:
        raise NotImplementedError

    return results
