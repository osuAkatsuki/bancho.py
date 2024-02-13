from __future__ import annotations

import textwrap
from typing import Any
from typing import TypedDict
from typing import cast

import app.state.services

# +---------+---------+------+-----+---------+-------+
# | Field   | Type    | Null | Key | Default | Extra |
# +---------+---------+------+-----+---------+-------+
# | map_id  | int     | NO   | PRI | NULL    |       |
# | pool_id | int     | NO   | PRI | NULL    |       |
# | mods    | int     | NO   |     | NULL    |       |
# | slot    | tinyint | NO   |     | NULL    |       |
# +---------+---------+------+-----+---------+-------+


class TourneyPoolMap(TypedDict):
    map_id: int
    pool_id: int
    mods: int
    slot: int


READ_PARAMS = textwrap.dedent(
    """\
        map_id, pool_id, mods, slot
    """,
)


async def create(map_id: int, pool_id: int, mods: int, slot: int) -> TourneyPoolMap:
    """Create a new map pool entry in the database."""
    query = f"""\
        INSERT INTO tourney_pool_maps (map_id, pool_id, mods, slot)
             VALUES (:map_id, :pool_id, :mods, :slot)
    """
    params: dict[str, Any] = {
        "map_id": map_id,
        "pool_id": pool_id,
        "mods": mods,
        "slot": slot,
    }
    await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM tourney_pool_maps
         WHERE map_id = :map_id
           AND pool_id = :pool_id
           AND mods = :mods
           AND slot = :slot
    """
    params = {
        "map_id": map_id,
        "pool_id": pool_id,
        "mods": mods,
        "slot": slot,
    }
    tourney_pool_map = await app.state.services.database.fetch_one(query, params)

    assert tourney_pool_map is not None
    return cast(TourneyPoolMap, dict(tourney_pool_map._mapping))


async def fetch_many(
    pool_id: int | None = None,
    mods: int | None = None,
    slot: int | None = None,
    page: int | None = 1,
    page_size: int | None = 50,
) -> list[TourneyPoolMap]:
    """Fetch a list of map pool entries from the database."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM tourney_pool_maps
         WHERE pool_id = COALESCE(:pool_id, pool_id)
           AND mods = COALESCE(:mods, mods)
           AND slot = COALESCE(:slot, slot)
    """
    params: dict[str, Any] = {
        "pool_id": pool_id,
        "mods": mods,
        "slot": slot,
    }
    if page and page_size:
        query += """\
            LIMIT :limit
           OFFSET :offset
        """
        params["limit"] = page_size
        params["offset"] = (page - 1) * page_size
    tourney_pool_maps = await app.state.services.database.fetch_all(query, params)
    return cast(
        list[TourneyPoolMap],
        [dict(tourney_pool_map._mapping) for tourney_pool_map in tourney_pool_maps],
    )


async def fetch_by_pool_and_pick(
    pool_id: int,
    mods: int,
    slot: int,
) -> TourneyPoolMap | None:
    """Fetch a map pool entry by pool and pick from the database."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM tourney_pool_maps
         WHERE pool_id = :pool_id
           AND mods = :mods
           AND slot = :slot
    """
    params: dict[str, Any] = {
        "pool_id": pool_id,
        "mods": mods,
        "slot": slot,
    }
    tourney_pool_map = await app.state.services.database.fetch_one(query, params)
    if tourney_pool_map is None:
        return None
    return cast(TourneyPoolMap, dict(tourney_pool_map._mapping))


async def delete_map_from_pool(pool_id: int, map_id: int) -> TourneyPoolMap | None:
    """Delete a map pool entry from a given tourney pool from the database."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM tourney_pool_maps
         WHERE pool_id = :pool_id
           AND map_id = :map_id
    """
    params: dict[str, Any] = {
        "pool_id": pool_id,
        "map_id": map_id,
    }
    tourney_pool_map = await app.state.services.database.fetch_one(query, params)
    if tourney_pool_map is None:
        return None

    query = f"""\
        DELETE FROM tourney_pool_maps
              WHERE pool_id = :pool_id
                AND map_id = :map_id
    """
    params = {
        "pool_id": pool_id,
        "map_id": map_id,
    }
    await app.state.services.database.execute(query, params)
    return cast(TourneyPoolMap, dict(tourney_pool_map._mapping))


async def delete_all_in_pool(pool_id: int) -> list[TourneyPoolMap]:
    """Delete all map pool entries from a given tourney pool from the database."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM tourney_pool_maps
         WHERE pool_id = :pool_id
    """
    params: dict[str, Any] = {
        "pool_id": pool_id,
    }
    tourney_pool_maps = await app.state.services.database.fetch_all(query, params)
    if not tourney_pool_maps:
        return []

    query = f"""\
        DELETE FROM tourney_pool_maps
              WHERE pool_id = :pool_id
    """
    params = {
        "pool_id": pool_id,
    }
    await app.state.services.database.execute(query, params)
    return cast(
        list[TourneyPoolMap],
        [dict(tourney_pool_map._mapping) for tourney_pool_map in tourney_pool_maps],
    )
