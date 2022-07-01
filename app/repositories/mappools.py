from __future__ import annotations

import logging
from datetime import datetime
from typing import MutableMapping
from typing import Optional
from typing import Union

import app.state.services
from app import repositories
from app.constants.mods import Mods
from app.objects.beatmap import Beatmap
from app.objects.match import MapPool

cache: MutableMapping[Union[int, str], MapPool] = {}  # {id/name: pool}


# TODO: not sure about this one
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

    cache[pool.id] = pool

    return pool


# read


def _fetch_by_id_cache(id: int) -> Optional[MapPool]:
    """Fetch a mappool from the cache by id."""
    return cache.get(id)


async def _fetch_by_id_database(id: int) -> Optional[MapPool]:
    """Fetch a mappool from the cache by id."""
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
    """Fetch a mappool from the cache, or database by name."""
    if mappool := _fetch_by_id_cache(id):
        return mappool

    if mappool := await _fetch_by_id_database(id):
        cache[mappool.id] = mappool
        cache[mappool.name] = mappool
        return mappool

    return None


def _fetch_by_name_cache(name: str) -> Optional[MapPool]:
    """Fetch a mappool from the cache by name."""
    return cache.get(name)


async def _fetch_by_name_database(name: str) -> Optional[MapPool]:
    """Fetch a mappool from the cache by name."""
    row = await app.state.services.database.fetch_one(
        "SELECT * FROM tourney_pools WHERE name = :name",
        {"name": name},
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


async def fetch_by_name(name: str) -> Optional[MapPool]:
    """Fetch a mappool from the cache, or database by name."""
    if mappool := _fetch_by_name_cache(name):
        return mappool

    if mappool := await _fetch_by_name_database(name):
        cache[mappool.id] = mappool
        cache[mappool.name] = mappool
        return mappool

    return None


async def fetch_all() -> set[MapPool]:
    """Fetch all mappools from the cache, or database."""
    if cache:
        return set(cache.values())
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


async def _populate_caches() -> None:
    """Populate the cache with all values from the database."""
    all_resources = await fetch_all()

    for resource in all_resources:
        cache[resource.id] = resource
        cache[resource.name] = resource

    return None


# update

# delete


async def delete(pool: MapPool) -> None:
    """Delete a mappool from the cache and database."""
    await app.state.services.database.execute(
        "DELETE FROM tourney_pools WHERE id = :pool_id",
        {"pool_id": pool.id},
    )

    await app.state.services.database.execute(
        "DELETE FROM tourney_pool_maps WHERE pool_id = :pool_id",
        {"pool_id": pool.id},
    )

    del cache[pool.id]
    del cache[pool.name]

    return None
