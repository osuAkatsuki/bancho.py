from __future__ import annotations

import textwrap
from datetime import datetime
from typing import Any
from typing import TypedDict
from typing import cast

import app.state.services

# +------------+-------------+------+-----+---------+----------------+
# | Field      | Type        | Null | Key | Default | Extra          |
# +------------+-------------+------+-----+---------+----------------+
# | id         | int         | NO   | PRI | NULL    | auto_increment |
# | name       | varchar(16) | NO   |     | NULL    |                |
# | created_at | datetime    | NO   |     | NULL    |                |
# | created_by | int         | NO   | MUL | NULL    |                |
# +------------+-------------+------+-----+---------+----------------+


class TourneyPool(TypedDict):
    id: int
    name: str
    created_at: datetime
    created_by: int


READ_PARAMS = textwrap.dedent(
    """\
        id, name, created_at, created_by
    """,
)


async def create(name: str, created_by: int) -> TourneyPool:
    """Create a new tourney pool entry in the database."""
    query = f"""\
        INSERT INTO tourney_pools (name, created_at, created_by)
             VALUES (:name, NOW(), :user_id)
    """
    params: dict[str, Any] = {
        "name": name,
        "user_id": created_by,
    }
    rec_id = await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM tourney_pools
         WHERE id = :id
    """
    params = {
        "id": rec_id,
    }
    tourney_pool = await app.state.services.database.fetch_one(query, params)

    assert tourney_pool is not None
    return cast(TourneyPool, dict(tourney_pool._mapping))


async def fetch_many(
    pool_id: int | None = None,
    created_by: int | None = None,
    page: int | None = 1,
    page_size: int | None = 50,
) -> list[TourneyPool]:
    query = f"""\
        SELECT {READ_PARAMS}
          FROM tourney_pools
          WHERE pool_id = COALESCE(:pool_id, pool_id)
            AND created_by = COALESCE(:created_by, created_by)
    """
    params: dict[str, Any] = {
        "pool_id": pool_id,
        "created_by": created_by,
    }
    if page and page_size:
        query += """\
            LIMIT :limit
           OFFSET :offset
        """
        params["limit"] = page_size
        params["offset"] = (page - 1) * page_size
    tourney_pools = await app.state.services.database.fetch_all(query, params)
    return [
        cast(TourneyPool, dict(tourney_pool._mapping)) for tourney_pool in tourney_pools
    ]


async def fetch_by_name(name: str) -> TourneyPool:
    """Fetch a tourney pool by name from the database."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM tourney_pools
         WHERE name = :name
    """
    params: dict[str, Any] = {
        "name": name,
    }
    tourney_pool = await app.state.services.database.fetch_one(query, params)

    assert tourney_pool is not None
    return cast(TourneyPool, dict(tourney_pool._mapping))


async def fetch_by_id(id: int) -> TourneyPool | None:
    """Fetch a tourney pool by id from the database."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM tourney_pools
         WHERE id = :id
    """
    params: dict[str, Any] = {
        "id": id,
    }
    tourney_pool = await app.state.services.database.fetch_one(query, params)
    return (
        None if tourney_pool is None else cast(TourneyPool, dict(tourney_pool._mapping))
    )


async def delete_by_id(id: int) -> TourneyPool | None:
    """Delete a tourney pool by id from the database."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM tourney_pools
         WHERE id = :id
    """
    params: dict[str, Any] = {
        "id": id,
    }
    tourney_pool = await app.state.services.database.fetch_one(query, params)
    if tourney_pool is None:
        return None

    query = f"""\
        DELETE FROM tourney_pools
              WHERE id = :id
    """
    params = {
        "id": id,
    }
    await app.state.services.database.execute(query, params)
    return cast(TourneyPool, dict(tourney_pool._mapping))
