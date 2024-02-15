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


async def create(userid: int, map_md5: str, rating: int) -> Rating:
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


async def fetch_many(
    userid: int | None = None,
    map_md5: str | None = None,
    page: int | None = 1,
    page_size: int | None = 50,
) -> list[Rating]:
    """Fetch multiple ratings, optionally with filter params and pagination."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM ratings
         WHERE userid = COALESCE(:userid, userid)
           AND map_md5 = COALESCE(:map_md5, map_md5)
    """
    params: dict[str, Any] = {
        "userid": userid,
        "map_md5": map_md5,
    }
    if page is not None and page_size is not None:
        query += """\
            LIMIT :limit
           OFFSET :offset
        """
        params["limit"] = page_size
        params["offset"] = (page - 1) * page_size
    ratings = await app.state.services.database.fetch_all(query, params)
    return cast(list[Rating], [dict(r._mapping) for r in ratings])


async def fetch_one(userid: int, map_md5: str) -> Rating | None:
    """Fetch a single rating for a given user and map."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM ratings
         WHERE userid = :userid
           AND map_md5 = :map_md5
    """
    params: dict[str, Any] = {
        "userid": userid,
        "map_md5": map_md5,
    }

    rating = await app.state.services.database.fetch_one(query, params)
    return cast(Rating, dict(rating._mapping)) if rating else None
