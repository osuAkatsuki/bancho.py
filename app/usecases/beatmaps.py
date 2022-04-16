from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

import app.repositories.beatmaps
import app.repositories.osuapi_v1
import app.settings
import app.state.services
import app.utils
from app.logging import Ansi
from app.logging import log
from app.objects import models
from app.objects.beatmap import Beatmap
from app.objects.player import Player


async def ensure_local_osu_file(
    osu_file_path: Path,
    bmap_id: int,
    bmap_md5: str,
) -> bool:
    """Ensure we have the latest .osu file locally,
    downloading it from the osu!api if required."""
    if (
        not osu_file_path.exists()
        or hashlib.md5(osu_file_path.read_bytes()).hexdigest() != bmap_md5
    ):
        # need to get the file from the osu!api
        if app.settings.DEBUG:
            log(f"Doing osu!api (.osu file) request {bmap_id}", Ansi.LMAGENTA)

        url = f"https://old.ppy.sh/osu/{bmap_id}"
        async with app.state.services.http.get(url) as resp:
            if resp.status != 200:
                if 400 <= resp.status < 500:
                    # client error, report this to cmyui
                    stacktrace = app.utils.get_appropriate_stacktrace()
                    await app.state.services.log_strange_occurrence(stacktrace)
                return False

            osu_file_path.write_bytes(await resp.read())

    return True


def bancho_to_osuapi_status(bancho_status: int) -> int:
    return {
        0: 0,
        2: 1,
        3: 2,
        4: 3,
        5: 4,
    }[bancho_status]


async def get_beatmap_info(
    player: Player,
    form_data: models.OsuBeatmapRequestForm,
) -> bytes:

    num_requests = len(form_data.Filenames) + len(form_data.Ids)
    log(f"{player} requested info for {num_requests} maps.", Ansi.LCYAN)

    ret = []

    async with app.state.services.database.connection() as db_conn:
        for idx, map_filename in enumerate(form_data.Filenames):
            # try getting the map from sql
            row = await db_conn.fetch_one(
                "SELECT id, set_id, status, md5 FROM maps WHERE filename = :filename",
                {"filename": map_filename},
            )

            if not row:
                continue

            row = dict(row)  # make mutable copy

            # convert from bancho.py -> osu!api status
            row["status"] = bancho_to_osuapi_status(row["status"])

            # try to get the user's grades on the map osu!
            # only allows us to send back one per gamemode,
            # so we'll just send back relax for the time being..
            # XXX: perhaps user-customizable in the future?
            grades = ["N", "N", "N", "N"]

            for score in await db_conn.fetch_all(
                "SELECT grade, mode FROM scores "
                "WHERE map_md5 = :map_md5 AND userid = :user_id "
                "AND mode = :mode AND status = 2",
                {
                    "map_md5": row["md5"],
                    "user_id": player.id,
                    "mode": player.status.mode,
                },
            ):
                grades[score["mode"]] = score["grade"]

            ret.append(
                "{i}|{id}|{set_id}|{md5}|{status}|{grades}".format(
                    **row, i=idx, grades="|".join(grades)
                ),
            )

    if form_data.Ids:  # still have yet to see this used
        await app.state.services.log_strange_occurrence(
            f"{player} requested map(s) info by id ({form_data.Ids})",
        )

    return "\n".join(ret).encode()


# TODO: perhaps transform these into map fetching by filename?


def _filename_exists_cache(filename: str) -> bool:
    """Fetch whether a map exists in the cache by filename."""
    for beatmap in app.repositories.beatmaps.cache.values():
        if filename == beatmap.filename:
            return True
    else:
        return False


async def _filename_exists_database(filename: str) -> bool:
    """Fetch whether a map exists in the database by filename."""
    return (
        await app.state.services.database.fetch_one(
            "SELECT 1 FROM maps WHERE filename = :filename",
            {"filename": filename},
        )
        is not None
    )


async def filename_exists(filename: str) -> bool:
    """Fetch whether a map exists by filename."""
    if _filename_exists_cache(filename):
        return True

    if await _filename_exists_database(filename):
        return True

    return False


async def fetch_rating(beatmap: Beatmap) -> Optional[float]:
    """Fetch the beatmap's rating from sql."""
    row = await app.state.services.database.fetch_one(
        "SELECT AVG(rating) rating FROM ratings WHERE map_md5 = :map_md5",
        {"map_md5": beatmap.md5},
    )

    if row is None:
        return None

    return row["rating"]
