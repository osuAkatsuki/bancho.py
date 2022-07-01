from __future__ import annotations

import logging
from typing import Mapping

import app.state.services
from app import repositories
from app.constants.mods import Mods
from app.objects.beatmap import Beatmap
from app.objects.match import MapPool

# create


async def create(name: str, created_by: int) -> MapPool:
    return await repositories.mappools.create(name, created_by)


# read
async def maps_from_sql(pool_id: int) -> Mapping[tuple[Mods, int], Beatmap]:
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


# update

# delete
