from __future__ import annotations

from typing import Mapping
from typing import MutableMapping
from typing import Optional

import app.repositories.beatmaps
import app.state.services
from app.constants.mods import Mods
from app.logging import Ansi
from app.logging import log
from app.objects.beatmap import Beatmap
from app.objects.match import MapPool

cache: MutableMapping[int, MapPool] = {}


# TODO: not sure about this one
async def _maps_from_sql(pool_id: int) -> Mapping[tuple[Mods, int], Beatmap]:
    """Retrieve all maps from sql to populate `self.maps`."""
    pool_maps: dict[tuple[Mods, int], Beatmap] = {}

    for row in await app.state.services.database.fetch_all(
        "SELECT map_id, mods, slot FROM tourney_pool_maps WHERE pool_id = :pool_id",
        {"pool_id": pool_id},
    ):
        map_id = row["map_id"]
        bmap = await app.repositories.beatmaps.fetch_by_id(map_id)

        if not bmap:
            # map not found? remove it from the
            # pool and log this incident to console.
            # NOTE: it's intentional that this removes
            # it from not only this pool, but all pools.
            # TODO: perhaps discord webhook?
            log(f"Removing {map_id} from pool {pool_id} (not found).", Ansi.LRED)

            await app.state.services.database.execute(
                "DELETE FROM tourney_pool_maps WHERE map_id = :map_id",
                {"map_id": map_id},
            )
            continue

        key: tuple[Mods, int] = (Mods(row["mods"]), row["slot"])
        pool_maps[key] = bmap

    return pool_maps


# create

# read


def _fetch_by_id_cache(id: int) -> Optional[MapPool]:
    """Fetch a channel from the cache by id."""
    return cache.get(id)


async def _fetch_by_id_database(id: int) -> Optional[MapPool]:
    """Fetch a channel from the cache by id."""
    row = await app.state.services.database.fetch_one(
        "SELECT * FROM tourney_pools WHERE id = :id",
        {"id": id},
    )
    if row is None:
        return None

    return MapPool(
        id=row["id"],
        name=row["name"],
        created_at=row["created_at"],
        created_by=row["created_by"],
        maps=await _maps_from_sql(row["id"]),
    )


async def fetch_by_id(id: int) -> Optional[MapPool]:
    """Fetch a channel from the cache, or database by name."""
    if channel := _fetch_by_id_cache(id):
        return channel

    if channel := await _fetch_by_id_database(id):
        return channel

    return None


async def fetch_all() -> set[MapPool]:
    """Fetch all mappools from the cache, or database."""
    pool_ids = {
        row["id"]
        for row in await app.state.services.database.fetch_all(
            "SELECT id FROM tourney_pools",
        )
    }

    mappools = set()
    for id in pool_ids:
        if mappool := fetch_by_id(id):  # should never be false
            mappools.add(mappool)

    return mappools


# update

# delete
