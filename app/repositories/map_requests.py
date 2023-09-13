from __future__ import annotations

import textwrap
from typing import Any
from typing import Optional

import app.state.services

# +--------------+------------------------+------+-----+---------+----------------+
# | Field        | Type                   | Null | Key | Default | Extra          |
# +--------------+------------------------+------+-----+---------+----------------+
# | id           | int                    | NO   | PRI | NULL    | auto_increment |
# | map_id       | int                    | NO   |     | osu!    |                |
# | player_id    | int                    | NO   |     | NULL    |                |
# | datetime     | datetime               | NO   |     | NULL    |                |
# | active       | tinyint(1)             | NO   |     | NULL    |                |
# +--------------+------------------------+------+-----+---------+----------------+

READ_PARAMS = textwrap.dedent(
    """\
        id, map_id, player_id, datetime, active
    """,
)


async def create(
    map_id: int,
    player_id: int,
    active: bool,
) -> dict[str, Any]:
    """Create a new map request entry in the database."""
    query = f"""\
        INSERT INTO map_requests (map_id, player_id, datetime, active)
             VALUES (:map_id, :player_id, NOW(), :active)
    """
    params = {
        "map_id": map_id,
        "player_id": player_id,
        "active": active,
    }
    rec_id = await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM map_requests
         WHERE id = :id
    """
    params = {
        "id": rec_id,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    assert rec is not None
    return dict(rec)


async def fetch_one(
    id: Optional[int] = None,
    map_id: Optional[int] = None,
    player_id: Optional[int] = None,
    active: Optional[int] = None,
) -> Optional[dict[str, Any]]:
    """Fetch a map request entry from the database."""
    if id is None and map_id is None and player_id is None and active is None:
        raise ValueError("Must provide at least one parameter.")

    query = f"""\
        SELECT {READ_PARAMS}
          FROM map_requests
         WHERE id = COALESCE(:id, id)
           AND map_id = COALESCE(:map_id, map_id)
           AND player_id = COALESCE(:player_id, player_id)
           AND active = COALESCE(:active, active)
    """
    params = {
        "id": id,
        "map_id": map_id,
        "player_id": player_id,
        "active": active,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    return dict(rec) if rec is not None else None


async def fetch_count(
    map_id: Optional[int] = None,
    player_id: Optional[int] = None,
    active: Optional[int] = None,
) -> int:
    """Fetch the number of map requests in the database."""
    query = """\
        SELECT COUNT(*) AS count
          FROM map_requests
        WHERE map_id = COALESCE(:map_id, map_id)
          AND player_id = COALESCE(:player_id, player_id)
          AND active = COALESCE(:active, active)
    """
    params = {
        "map_id": map_id,
        "player_id": player_id,
        "active": active,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    assert rec is not None
    return rec["count"]


async def fetch_all(
    map_id: Optional[int] = None,
    player_id: Optional[int] = None,
    active: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Fetch a list of map requests from the database."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM map_requests
         WHERE map_id = COALESCE(:map_id, map_id)
          AND player_id = COALESCE(:player_id, player_id)
          AND active = COALESCE(:active, active)
    """
    params = {
        "map_id": map_id,
        "player_id": player_id,
        "active": active,
    }
    recs = await app.state.services.database.fetch_all(query, params)
    return [dict(rec) for rec in recs]


async def update(
    map_ids: Optional[list[Any]] = None,
    player_id: Optional[int] = None,
    active: Optional[int] = None,
) -> Optional[dict[str, Any]]:
    """Update a map request entry in the database."""
    query = """\
        UPDATE map_requests
           SET player_id = COALESCE(:player_id, player_id),
               active = COALESCE(:active, active)
         WHERE map_id IN :map_ids
    """
    params = {
        "map_ids": map_ids,
        "player_id": player_id,
        "active": active,
    }
    await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM map_requests
        WHERE map_id IN :map_ids
    """
    params = {
        "map_ids": map_ids,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    return dict(rec) if rec is not None else None


async def delete(id: int) -> Optional[dict[str, Any]]:
    """Delete a map request entry from the database."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM map_requests
        WHERE id = :id
    """
    params = {
        "id": id,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    if rec is None:
        return None

    query = """\
        DELETE FROM map_requests
              WHERE id = :id
    """
    params = {
        "id": id,
    }
    await app.state.services.database.execute(query, params)
    return dict(rec)
