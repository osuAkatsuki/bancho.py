from __future__ import annotations

import textwrap
from typing import Any
from typing import TypedDict
from typing import cast

import app.state.services

# +---------+----------+------+-----+---------+-------+
# | Field   | Type     | Null | Key | Default | Extra |
# +---------+----------+------+-----+---------+-------+
# | userid  | int      | NO   | PRI | NULL    |       |
# | map_md5 | char(32) | NO   | PRI | NULL    |       |
# | rating  | tinyint  | NO   |     | NULL    |       |
# +---------+----------+------+-----+---------+-------+

READ_PARAMS = textwrap.dedent(
    """\
        userid, map_md5, rating
    """,
)


class Rating(TypedDict):
    userid: int
    map_md5: str
    rating: int


async def create(
    userid: int,
    map_md5: str,
    rating: int,
) -> Rating:
    """Create a new rating."""
    query = """\
        INSERT INTO ratings (userid, map_md5, rating)
             VALUES (:userid, :map_md5, :rating)
    """
    params: dict[str, Any] = {
        "userid": userid,
        "map_md5": map_md5,
        "rating": rating,
    }
    await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM ratings
         WHERE userid = :userid
           AND map_md5 = :map_md5
    """
    params = {
        "userid": userid,
        "map_md5": map_md5,
    }
    _rating = await app.state.services.database.fetch_one(query, params)

    assert _rating is not None
    return cast(Rating, dict(_rating._mapping))


async def fetch_all(map_md5: str) -> list[Rating]:
    """Fetch all ratings for a map."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM ratings
         WHERE map_md5 = :map_md5
    """
    params: dict[str, Any] = {
        "map_md5": map_md5,
    }

    ratings = await app.state.services.database.fetch_all(query, params)
    return cast(list[Rating], [dict(r._mapping) for r in ratings])


async def has_previous_rating(map_md5: str, userid: int) -> bool:
    """Check if a user has previously rated a map."""
    query = f"""\
        SELECT 1
          FROM ratings
         WHERE map_md5 = :map_md5
           AND userid = :userid
    """
    params: dict[str, Any] = {
        "map_md5": map_md5,
        "userid": userid,
    }

    has_previous_rating = await app.state.services.database.fetch_one(query, params)
    return bool(has_previous_rating)
