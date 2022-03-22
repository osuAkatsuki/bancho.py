from __future__ import annotations

import app.state.services
from app.constants.gamemodes import GameMode
from app.objects.beatmap import Beatmap
from app.objects.leaderboard import Leaderboard
from app.objects.score import Score


async def create(beatmap: Beatmap, mode: GameMode) -> Leaderboard:
    leaderboard = Leaderboard(mode)

    rows = await app.state.services.database.fetch_all(
        "SELECT id, map_md5, userid, pp, score, "
        "max_combo, mods, acc, n300, n100, n50, "
        "nmiss, ngeki, nkatu, grade, perfect, "
        "status, mode, play_time, "
        "time_elapsed, client_flags, online_checksum "
        "FROM scores WHERE map_md5 = :map_md5 AND status = 2 "
        "AND mode = :mode",
        {"map_md5": beatmap.md5, "mode": mode.value},
    )

    for row in rows:
        score_obj = await Score.from_row(row, calculate_rank=False)
        leaderboard.scores.append(score_obj)

    leaderboard.sort()
    return leaderboard


async def fetch(beatmap: Beatmap, mode: GameMode) -> Leaderboard:
    if leaderboard := beatmap.leaderboards.get(mode):
        return leaderboard

    leaderboard = await create(beatmap, mode)
    beatmap.leaderboards[mode] = leaderboard

    return leaderboard
