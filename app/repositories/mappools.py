from __future__ import annotations

import logging
from datetime import datetime
from typing import MutableMapping
from typing import Optional

import app.state.services
from app import repositories
from app.constants.mods import Mods
from app.objects.beatmap import Beatmap
from app.objects.match import MapPool

## in-memory cache

id_cache: MutableMapping[int, MapPool] = {}
name_cache: MutableMapping[str, MapPool] = {}


def add_to_cache(map_pool: MapPool) -> None:
    id_cache[map_pool.id] = map_pool
    name_cache[map_pool.name] = map_pool


def remove_from_cache(map_pool: MapPool) -> None:
    del id_cache[map_pool.id]
    del name_cache[map_pool.name]


## helpers


async def _maps_from_sql(pool_id: int) -> MutableMapping[tuple[Mods, int], Beatmap]:
    """Retrieve all maps from sql to populate `self.maps`."""
    pool_maps: dict[tuple[Mods, int], Beatmap] = {}

    for row in await app.state.services.database.fetch_all(
        "SELECT map_id, mods, slot FROM tourney_pool_maps WHERE pool_id = :pool_id",
        {"pool_id": pool_id},
    ):
        map_id = row["map_id"]
        bmap = await repositories.beatmaps.fetch_by_id(map_id)

        if not bmap:
            # map not found? remove it from the
            # pool and log this incident to console.
            # NOTE: it's intentional that this removes
            # it from not only this pool, but all pools.
            # TODO: perhaps discord webhook?
            logging.warning(f"Removing {map_id} from pool {pool_id} (not found).")

            await app.state.services.database.execute(
                "DELETE FROM tourney_pool_maps WHERE map_id = :map_id",
                {"map_id": map_id},
            )
            continue

        key: tuple[Mods, int] = (Mods(row["mods"]), row["slot"])
        pool_maps[key] = bmap

    return pool_maps


# create


async def create(name: str, created_by: int) -> MapPool:
    """Create a mappool in cache and the database."""
    created_at = datetime.now()

    pool_id = await app.state.services.database.execute(
        "INSERT INTO tourney_pools "
        "(name, created_at, created_by) "
        "VALUES (:name, :created_at, :created_by)",
        {"name": name, "created_at": created_at, "created_by": created_by},
    )

    pool = MapPool(
        id=pool_id,
        name=name,
        created_at=created_at,
        created_by=created_by,
        maps={},
    )

    id_cache[pool.id] = pool
    name_cache[pool.name] = pool

    return pool


# read


async def fetch_by_id(id: int) -> Optional[MapPool]:
    """Fetch a mappool by id number."""
    if map_pool := id_cache.get(id):
        return map_pool

    row = await app.state.services.database.fetch_one(
        "SELECT * FROM tourney_pools WHERE id = :id",
        {"id": id},
    )
    if row is None:
        return None

    map_pool = MapPool(
        id=row["id"],
        name=row["name"],
        created_at=row["created_at"],
        created_by=row["created_by"],
        maps=await _maps_from_sql(row["id"]),
    )

    add_to_cache(map_pool)
    return map_pool


async def fetch_by_name(name: str) -> Optional[MapPool]:
    """Fetch a mappool by name."""
    if map_pool := name_cache.get(name):
        return map_pool

    row = await app.state.services.database.fetch_one(
        "SELECT * FROM tourney_pools WHERE name = :name",
        {"name": name},
    )
    if row is None:
        return None

    map_pool = MapPool(
        id=row["id"],
        name=row["name"],
        created_at=row["created_at"],
        created_by=row["created_by"],
        maps=await _maps_from_sql(row["id"]),
    )

    return map_pool


async def fetch_all() -> set[MapPool]:
    """Fetch all mappools from the cache, or database."""
    if id_cache:
        return set(id_cache.values())
    else:
        pool_ids = {
            row["id"]
            for row in await app.state.services.database.fetch_all(
                "SELECT id FROM tourney_pools",
            )
        }

        mappools = set()
        for id in pool_ids:
            if mappool := await fetch_by_id(id):  # should never be false
                mappools.add(mappool)

    return mappools


# update

# delete


async def delete(pool: MapPool) -> None:
    """Delete a mappool."""
    await app.state.services.database.execute(
        "DELETE FROM tourney_pools WHERE id = :pool_id",
        {"pool_id": pool.id},
    )

    await app.state.services.database.execute(
        "DELETE FROM tourney_pool_maps WHERE pool_id = :pool_id",
        {"pool_id": pool.id},
    )

    del id_cache[pool.id]
    del name_cache[pool.name]

    return None
