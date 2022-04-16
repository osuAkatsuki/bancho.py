from __future__ import annotations

from typing import Optional
from typing import Union

import app.repositories.osuapi_v1
import app.state.services
from app.objects.beatmap import Beatmap
from app.objects.beatmap import RankedStatus


cache: dict[Union[str, int], Beatmap] = {}

## create

## read

# fetch by md5


def _fetch_by_md5_cache(md5: str) -> Optional[Beatmap]:
    if beatmap := cache.get(md5):
        return beatmap


async def _fetch_by_md5_database(md5: str) -> Optional[Beatmap]:
    row = await app.state.services.database.fetch_one(
        "SELECT md5, id, set_id, "
        "artist, title, version, creator, "
        "filename, last_update, total_length, "
        "max_combo, status, frozen, "
        "plays, passes, mode, bpm, "
        "cs, od, ar, hp, diff "
        "FROM maps "
        "WHERE md5 = :md5",
        {"md5": md5},
    )
    if row is None:
        return None

    return Beatmap(
        map_set=None,  # type: ignore
        **row,
    )


async def _fetch_by_md5_osuapi(md5: str) -> Optional[Beatmap]:
    api_data = await app.repositories.osuapi_v1.get_beatmaps(h=md5)

    if api_data is None:
        return None

    # TODO: is it possible for this to be a map we already have?
    #       might need to vary logic based on frozen status

    return Beatmap.from_osuapi_response(api_data[0])


async def fetch_by_md5(md5: str) -> Optional[Beatmap]:
    """Fetch a map from the cache, database, or osuapi by md5."""
    if beatmap := _fetch_by_md5_cache(md5):
        return beatmap

    if beatmap := await _fetch_by_md5_database(md5):
        cache[beatmap.md5] = beatmap
        cache[beatmap.id] = beatmap
        return beatmap

    if beatmap := await _fetch_by_md5_osuapi(md5):
        cache[beatmap.md5] = beatmap
        cache[beatmap.id] = beatmap
        return beatmap

    return None


# fetch by id


def _fetch_by_id_cache(id: int) -> Optional[Beatmap]:
    if beatmap := cache.get(id):
        return beatmap


async def _fetch_by_id_database(id: int) -> Optional[Beatmap]:
    row = await app.state.services.database.fetch_one(
        "SELECT id, id, set_id, "
        "artist, title, version, creator, "
        "filename, last_update, total_length, "
        "max_combo, status, frozen, "
        "plays, passes, mode, bpm, "
        "cs, od, ar, hp, diff "
        "FROM maps "
        "WHERE id = :id",
        {"id": id},
    )
    if row is None:
        return None

    return Beatmap(
        map_set=None,  # type: ignore
        **row,
    )


async def _fetch_by_id_osuapi(id: int) -> Optional[Beatmap]:
    api_data = await app.repositories.osuapi_v1.get_beatmaps(b=id)

    if api_data is None:
        return None

    # TODO: is it possible for this to be a map we already have?
    #       might need to vary logic based on frozen status

    return Beatmap.from_osuapi_response(api_data[0])


async def fetch_by_id(id: int) -> Optional[Beatmap]:
    """Fetch a map from the cache, database, or osuapi by id."""
    if beatmap := _fetch_by_id_cache(id):
        return beatmap

    if beatmap := await _fetch_by_id_database(id):
        cache[beatmap.id] = beatmap
        cache[beatmap.id] = beatmap
        return beatmap

    if beatmap := await _fetch_by_id_osuapi(id):
        cache[beatmap.md5] = beatmap
        cache[beatmap.id] = beatmap
        return beatmap

    return None


## update


async def update_status(beatmap_id: int, new_status: RankedStatus) -> None:
    """Update a beatmap to a new ranked status in the database."""

    await app.state.services.database.execute(
        "UPDATE maps SET status = :status, frozen = 1 WHERE id = :map_id",
        {"status": new_status, "map_id": beatmap_id},
    )


## delete
