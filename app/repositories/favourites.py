from __future__ import annotations

import textwrap
from datetime import datetime
from typing import Any
from typing import TypedDict
from typing import cast

import app.state.services

# +--------------+------------------------+------+-----+---------+----------------+
# | Field        | Type                   | Null | Key | Default | Extra          |
# +--------------+------------------------+------+-----+---------+----------------+
# | userid       | int                    | NO   | PRI | NULL    |                |
# | setid        | int                    | NO   |     | NULL    |                |
# | created_at   | int                    | NO   |     | 0       |                |
# +--------------+------------------------+------+-----+---------+----------------+

READ_PARAMS = textwrap.dedent(
    """\
        userid, setid, created_at
    """,
)


class Favourite(TypedDict):
    userid: int
    setid: int
    created_at: int


async def create(
    userid: int,
    setid: int,
) -> Favourite:
    """Create a new favourite mapset entry in the database."""
    query = f"""\
        INSERT INTO favourites (userid, setid, created_at)
             VALUES (:userid, :setid, UNIX_TIMESTAMP())
    """
    params: dict[str, Any] = {
        "userid": userid,
        "setid": setid,
    }
    rec_id = await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM favourites
         WHERE userid = :userid
    """
    params = {
        "userid": rec_id,
    }
    favourite = await app.state.services.database.fetch_one(query, params)

    assert favourite is not None
    return cast(Favourite, dict(favourite._mapping))


async def fetch_all(userid: int) -> list[Favourite]:
    """Fetch all favourites from a player."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM favourites
         WHERE userid = :userid
    """
    params: dict[str, Any] = {
        "userid": userid,
    }

    favourites = await app.state.services.database.fetch_all(query, params)
    return cast(list[Favourite], [dict(f._mapping) for f in favourites])


async def is_already_favourite(userid: int, setid: int) -> bool:
    """Check if a mapset is already a favourite."""
    query = f"""\
        SELECT 1
          FROM favourites
         WHERE userid = :userid
           AND setid = :setid
    """
    params: dict[str, Any] = {
        "userid": userid,
        "setid": setid,
    }

    is_already_favourite = await app.state.services.database.fetch_one(query, params)
    return bool(is_already_favourite)
