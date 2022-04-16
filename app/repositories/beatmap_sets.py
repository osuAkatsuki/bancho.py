from __future__ import annotations

from datetime import datetime
from typing import Optional

import app.repositories.beatmap_sets
import app.repositories.osuapi_v1
import app.state.services
from app.logging import Ansi
from app.logging import log
from app.objects.beatmap import Beatmap
from app.objects.beatmap import BeatmapSet
from app.objects.beatmap import RankedStatus

cache: dict[int, BeatmapSet] = {}


def _fetch_by_id_cache(id: int) -> Optional[BeatmapSet]:
    """Fetch a beatmap set from the cache."""
    return cache.get(id)


async def _fetch_by_id_database(id: int) -> Optional[BeatmapSet]:
    """Fetch a beatmap set from the database."""
    async with app.state.services.database.connection() as db_conn:
        last_osuapi_check = await db_conn.fetch_val(
            "SELECT last_osuapi_check FROM mapsets WHERE id = :set_id",
            {"set_id": id},
        )

        if last_osuapi_check is None:
            return None

        beatmap_set = BeatmapSet(id=id, last_osuapi_check=last_osuapi_check)

        for row in await db_conn.fetch_all(
            "SELECT md5, id, set_id, "
            "artist, title, version, creator, "
            "filename, last_update, total_length, "
            "max_combo, status, frozen, "
            "plays, passes, mode, bpm, "
            "cs, od, ar, hp, diff "
            "FROM maps "
            "WHERE set_id = :set_id",
            {"set_id": id},
        ):
            bmap = Beatmap(**row, map_set=beatmap_set)
            beatmap_set.maps.append(bmap)

    return beatmap_set


async def _fetch_by_id_osuapi(id: int) -> Optional[BeatmapSet]:
    """Fetch a mapset from the osu!api by set id."""
    api_data = await app.repositories.osuapi_v1.get_beatmaps(s=id)

    if api_data is None:
        return None

    beatmap_set = BeatmapSet(id=id, last_osuapi_check=datetime.now())

    # XXX: pre-mapset bancho.py support
    # select all current beatmaps
    # that're frozen in the db
    res = await app.state.services.database.fetch_all(
        "SELECT id, status FROM maps WHERE set_id = :set_id AND frozen = 1",
        {"set_id": id},
    )

    current_maps = {row["id"]: row["status"] for row in res}

    for api_bmap in api_data:
        # newer version available for this map
        beatmap = Beatmap.from_osuapi_response(api_bmap)

        if beatmap is None:
            log(
                f"Failed to parse beatmap from osu!api response: {api_bmap}",
                Ansi.LRED,
            )
            continue

        if beatmap.id in current_maps:
            # map status is currently frozen
            beatmap.status = RankedStatus(current_maps[beatmap.id])
            beatmap.frozen = True
        else:
            beatmap.frozen = False

        # (some implementation-specific stuff not given by api)
        beatmap.passes = 0
        beatmap.plays = 0

        beatmap.set = beatmap_set
        beatmap_set.maps.append(beatmap)

    await app.state.services.database.execute(
        "REPLACE INTO mapsets "
        "(server, id, last_osuapi_check) "
        'VALUES ("osu!", :id, :last_osuapi_check)',
        {"id": beatmap_set.id, "last_osuapi_check": beatmap_set.last_osuapi_check},
    )

    await app.repositories.beatmap_sets.save_to_sql(beatmap_set)
    return beatmap_set


async def fetch_by_id(id: int) -> Optional[BeatmapSet]:
    """Fetch a beatmap set from the cache, database, or osuapi by id."""
    if beatmap_set := _fetch_by_id_cache(id):
        return beatmap_set

    if beatmap_set := await _fetch_by_id_database(id):
        cache[beatmap_set.id] = beatmap_set
        # TODO: when should we cache the individual beatmaps?
        return beatmap_set

    if beatmap_set := await _fetch_by_id_osuapi(id):
        cache[beatmap_set.id] = beatmap_set
        # TODO: when should we cache the individual beatmaps?
        return beatmap_set

    return None


async def save_to_sql(beatmap_set: BeatmapSet) -> None:
    """Save the object's attributes into the database."""
    await app.state.services.database.execute_many(
        "REPLACE INTO maps ("
        "server, md5, id, set_id, "
        "artist, title, version, creator, "
        "filename, last_update, total_length, "
        "max_combo, status, frozen, "
        "plays, passes, mode, bpm, "
        "cs, od, ar, hp, diff"
        ") VALUES ("
        '"osu!", :md5, :id, :set_id, '
        ":artist, :title, :version, :creator, "
        ":filename, :last_update, :total_length, "
        ":max_combo, :status, :frozen, "
        ":plays, :passes, :mode, :bpm, "
        ":cs, :od, :ar, :hp, :diff"
        ")",
        [
            {
                "md5": bmap.md5,
                "id": bmap.id,
                "set_id": bmap.set_id,
                "artist": bmap.artist,
                "title": bmap.title,
                "version": bmap.version,
                "creator": bmap.creator,
                "filename": bmap.filename,
                "last_update": bmap.last_update,
                "total_length": bmap.total_length,
                "max_combo": bmap.max_combo,
                "status": bmap.status,
                "frozen": bmap.frozen,
                "plays": bmap.plays,
                "passes": bmap.passes,
                "mode": bmap.mode,
                "bpm": bmap.bpm,
                "cs": bmap.cs,
                "od": bmap.od,
                "ar": bmap.ar,
                "hp": bmap.hp,
                "diff": bmap.diff,
            }
            for bmap in beatmap_set.maps
        ],
    )
