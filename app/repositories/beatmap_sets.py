from __future__ import annotations

import logging
from datetime import datetime
from typing import MutableMapping
from typing import Optional

import app.state.services
from app import repositories
from app.objects.beatmap import Beatmap
from app.objects.beatmap import BeatmapSet
from app.objects.beatmap import RankedStatus

# TODO: this design is inconsistent with other repositories (for now)
#       as i had been going in a different direction before i saw this
#
#       now i'm rethinking how i want to split up logic to interact
#       with different data sources (e.g. memory, database, osu!api here)
#
#       need more time to think about it


## in-memory cache

id_cache: MutableMapping[int, BeatmapSet] = {}


def add_to_cache(beatmap_set: BeatmapSet) -> None:
    id_cache[beatmap_set.id] = beatmap_set

    for beatmap in beatmap_set.maps:
        repositories.beatmaps.add_to_cache(beatmap)


def remove_from_cache(beatmap_set: BeatmapSet) -> None:
    del id_cache[beatmap_set.id]

    for beatmap in beatmap_set.maps:
        repositories.beatmaps.remove_from_cache(beatmap)


## create
# TODO: beatmap submission

## read


def _fetch_by_id_cache(id: int) -> Optional[BeatmapSet]:
    """Fetch a beatmap set from the cache."""
    return id_cache.get(id)


async def _fetch_by_id_database(id: int) -> Optional[BeatmapSet]:
    """Fetch a beatmap set from the database."""
    async with app.state.services.database.connection() as db_conn:
        last_osuapi_check = await db_conn.fetch_val(
            "SELECT last_osuapi_check FROM mapsets WHERE id = :set_id",
            {"set_id": id},
        )

        if last_osuapi_check is None:
            return None

        return BeatmapSet(
            id,
            last_osuapi_check,
            maps=[
                Beatmap(**row)
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
                )
            ],
        )


async def _fetch_by_id_osuapi(id: int) -> Optional[BeatmapSet]:
    """Fetch a mapset from the osu!api by set id."""
    api_data = await repositories.osuapi_v1.get_beatmaps(s=id)

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
            logging.error(f"Failed to parse beatmap from osu!api response: {api_bmap}")
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

        beatmap_set.maps.append(beatmap)

    await app.state.services.database.execute(
        "REPLACE INTO mapsets "
        "(server, id, last_osuapi_check) "
        'VALUES ("osu!", :id, :last_osuapi_check)',
        {"id": beatmap_set.id, "last_osuapi_check": beatmap_set.last_osuapi_check},
    )

    await replace(beatmap_set)
    return beatmap_set


async def fetch_by_id(id: int) -> Optional[BeatmapSet]:
    """Fetch a beatmap set from the cache, database, or osuapi by id."""
    if beatmap_set := _fetch_by_id_cache(id):
        return beatmap_set

    if beatmap_set := await _fetch_by_id_database(id):
        add_to_cache(beatmap_set)

        return beatmap_set

    if beatmap_set := await _fetch_by_id_osuapi(id):
        add_to_cache(beatmap_set)

        return beatmap_set

    return None


## update


async def update_status(id: int, new_status: RankedStatus) -> None:
    """Update all beatmaps in a set to a new ranked status in the database."""

    await app.state.services.database.execute(
        "UPDATE maps SET status = :status, frozen = 1 WHERE set_id = :set_id",
        {"status": new_status, "set_id": id},
    )

    if beatmap_set := id_cache.get(id):
        for beatmap in beatmap_set.maps:
            beatmap.status = new_status


async def replace(beatmap_set: BeatmapSet) -> None:
    """Replace the existing beatmap's attributes with new ones."""
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

    # update cached data
    remove_from_cache(beatmap_set)
    new_beatmap_set = await fetch_by_id(beatmap_set.id)
    assert new_beatmap_set is not None
    add_to_cache(new_beatmap_set)


## delete
# TODO: beatmap submission
