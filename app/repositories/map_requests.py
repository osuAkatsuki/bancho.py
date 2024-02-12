from __future__ import annotations

import textwrap
from datetime import datetime
from typing import Any
from typing import TypedDict
from typing import cast

import app.state.services
from app._typing import UNSET
from app._typing import _UnsetSentinel

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


class MapRequest(TypedDict):
    id: int
    map_id: int
    player_id: int
    datetime: datetime
    active: bool


async def create(
    map_id: int,
    player_id: int,
    active: bool,
) -> MapRequest:
    """Create a new map request entry in the database."""
    query = f"""\
        INSERT INTO map_requests (map_id, player_id, datetime, active)
             VALUES (:map_id, :player_id, NOW(), :active)
    """
    params: dict[str, Any] = {
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
    map_request = await app.state.services.database.fetch_one(query, params)

    assert map_request is not None
    return cast(MapRequest, dict(map_request._mapping))


async def fetch_one(
    id: int | None = None,
    map_id: int | None = None,
    player_id: int | None = None,
    active: int | None = None,
) -> MapRequest | None:
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
    params: dict[str, Any] = {
        "id": id,
        "map_id": map_id,
        "player_id": player_id,
        "active": active,
    }
    map_request = await app.state.services.database.fetch_one(query, params)

    return (
        cast(MapRequest, dict(map_request._mapping))
        if map_request is not None
        else None
    )


async def fetch_count(
    map_id: int | None = None,
    player_id: int | None = None,
    active: int | None = None,
) -> int:
    """Fetch the number of map requests in the database."""
    query = """\
        SELECT COUNT(*) AS count
          FROM map_requests
        WHERE map_id = COALESCE(:map_id, map_id)
          AND player_id = COALESCE(:player_id, player_id)
          AND active = COALESCE(:active, active)
    """
    params: dict[str, Any] = {
        "map_id": map_id,
        "player_id": player_id,
        "active": active,
    }

    rec = await app.state.services.database.fetch_one(query, params)
    assert rec is not None
    return cast(int, rec._mapping["count"])


async def fetch_all(
    map_id: int | None = None,
    player_id: int | None = None,
    active: int | None = None,
) -> list[MapRequest]:
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

    map_requests = await app.state.services.database.fetch_all(query, params)
    return cast(list[MapRequest], [dict(m._mapping) for m in map_requests])


async def mark_batch_as_inactive(map_ids: list[Any]) -> list[MapRequest]:
    """Mark a map request as inactive."""
    query = f"""\
        UPDATE map_requests
           SET active = False
         WHERE map_id IN :map_ids
    """
    params = {"map_id": map_ids}
    await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM map_requests
        WHERE map_id IN :map_ids
    """
    params = {
        "map_ids": map_ids,
    }
    map_requests = await app.state.services.database.fetch_all(query, params)
    return cast(list[MapRequest], [dict(m._mapping) for m in map_requests])
