from __future__ import annotations

from typing import Optional
from typing import Union

import app.repositories.osuapi_v1  # TODO: refactor this requirement out
import app.state.services
from app.objects.beatmap import Beatmap
from app.objects.beatmap import RankedStatus

BeatmapID = int
BeatmapMD5 = str

KeyTypes = Union[BeatmapID, BeatmapMD5]

cache: dict[KeyTypes, Beatmap] = {}

## create
# TODO: beatmap submission

## read


# low level api
# allows for fetching based on any supported key


def _fetch_by_key_cache(val: KeyTypes) -> Optional[Beatmap]:
    """Fetch a map from the cache by any supported key."""
    if beatmap := cache.get(val):
        return beatmap

    return None


async def _fetch_by_key_database(key: str, val: KeyTypes) -> Optional[Beatmap]:
    """Fetch a map from the database by any supported key."""
    row = await app.state.services.database.fetch_one(
        "SELECT md5, id, set_id, "
        "artist, title, version, creator, "
        "filename, last_update, total_length, "
        "max_combo, status, frozen, "
        "plays, passes, mode, bpm, "
        "cs, od, ar, hp, diff "
        "FROM maps "
        f"WHERE {key} = :val",
        {"val": val},
    )
    if row is None:
        return None

    return Beatmap(
        map_set=None,  # type: ignore
        **row,
    )


async def _fetch_by_key_osuapi(key: str, val: KeyTypes) -> Optional[Beatmap]:
    """Fetch a map from the osuapi by any supported key."""
    if key == "md5":
        params = {"h": val}
    elif key == "id":
        params = {"b": val}
    else:
        raise NotImplementedError

    api_data = await app.repositories.osuapi_v1.get_beatmaps(**params)

    if api_data is None:
        return None

    # TODO: is it possible for this to be a map we already have?
    #       might need to vary logic based on frozen status

    try:
        return Beatmap.from_osuapi_response(api_data[0])
    except IndexError:
        breakpoint()


async def _fetch_by_key(key: str, val: KeyTypes) -> Optional[Beatmap]:
    """Fetch a map from the cache, database, or osuapi by any supported key."""
    if beatmap := _fetch_by_key_cache(val):
        return beatmap

    if beatmap := await _fetch_by_key_database(key, val):
        cache[beatmap.md5] = beatmap
        cache[beatmap.id] = beatmap
        return beatmap

    if beatmap := await _fetch_by_key_osuapi(key, val):
        cache[beatmap.md5] = beatmap
        cache[beatmap.id] = beatmap
        return beatmap

    return None


# high level api


async def fetch_by_md5(md5: str) -> Optional[Beatmap]:
    """Fetch a beatmap from the cache, database, or osuapi by md5."""
    return await _fetch_by_key("md5", md5)


async def fetch_by_id(id: int) -> Optional[Beatmap]:
    """Fetch a beatmap from the cache, database, or osuapi by id."""
    return await _fetch_by_key("id", id)


## update


async def update_status(beatmap_id: int, new_status: RankedStatus) -> None:
    """Update a beatmap to a new ranked status in the database."""

    await app.state.services.database.execute(
        "UPDATE maps SET status = :status, frozen = 1 WHERE id = :map_id",
        {"status": new_status, "map_id": beatmap_id},
    )


## delete
# TODO: beatmap submission
