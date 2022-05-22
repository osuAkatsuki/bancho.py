from __future__ import annotations
import asyncio

import math
import subprocess
from typing import Optional
from typing import TypedDict
import app

import orjson

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

async def calculate_performances(osu_file_path: str, mode: int, mods: Optional[int], scores: list[ScoreDifficultyParams]) -> list[DifficultyRating]:
    results: list[DifficultyRating] = []

    for score in scores:
        cmd = generate_cmd(osu_file_path, mode, mods, score)
        app.logging.log(f"[PP Calc] Prepared | calc {osu_file_path} : {cmd}", Ansi.GRAY)
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)
        app.logging.log(f"[PP Calc] Spawned | calc {osu_file_path}", Ansi.GRAY)
        stdout, stderr = await proc.communicate()
        app.logging.log(f"[PP Calc] Returned | calc {osu_file_path}", Ansi.GRAY)
        if proc.returncode != 0:
            app.logging.log(f"[PP Calc] Error occurred when calculating map {osu_file_path}: {stderr.decode()}", Ansi.LRED)
            results.append({
                "performance": 0.0,
                "star_rating": 0.0,
            })
            continue
        try:
            obj = orjson.loads(stdout.decode())
            if mode == 4:
                pp = obj["performance_attributes"]["aim"]
            elif mode == 8:
                pp = obj["performance_attributes"]["speed"]
            else:
                pp = obj["performance_attributes"]["pp"]
            sr = obj["difficulty_attributes"]["star_rating"]
            if math.isnan(pp) or math.isinf(pp) or math.isnan(sr) or math.isinf(sr):
                app.logging.log(f"[PP Calc] Abnormal value when calculating map {osu_file_path}", Ansi.LRED)
                pp = 0.0
                sr = 0.0
        except orjson.JSONDecodeError:
            app.logging.log(f"[PP Calc] JSON decode error when calculating map {osu_file_path}", Ansi.LRED)
            pp = 0.0
            sr = 0.0
        app.logging.log(f"[PP Calc] Parsed | calc {osu_file_path}", Ansi.GRAY)
        results.append({
            "performance": pp,
            "star_rating": sr,
        })
    
    return results

def generate_cmd(osu_file_path: str, mode: int, mods: Optional[int], score: ScoreDifficultyParams) -> list[str]:
    if mode in (0, 4, 8):
        mode_str = "osu"
    elif mode in (1, 5):
        mode_str = "taiko"
    elif mode in (2, 6):
        mode_str = "catch"
    else:
        mode_str = "mania"

    cmd = [OSU_TOOLS_EXEC_PATH, "simulate", mode_str, "-j"]

    if mods is not None:
        cmd.append("-lm")
        cmd.append(str(mods))

    if mode_str == "mania":
        if score.get("score") is not None:
            cmd.append("-s")
            cmd.append(str(score.get("score")))
    else:
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

    return cmd