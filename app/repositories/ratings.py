from __future__ import annotations

from typing import TypedDict
from typing import cast

from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import insert
from sqlalchemy import select
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.dialects.mysql import TINYINT

import app.state.services
from app.repositories import Base


class RatingsTable(Base):
    __tablename__ = "ratings"

    userid = Column("userid", Integer, nullable=False, primary_key=True)
    map_md5 = Column("map_md5", CHAR(length=32), nullable=False, primary_key=True)
    rating = Column("rating", TINYINT(2), nullable=False)


READ_PARAMS = (
    RatingsTable.userid,
    RatingsTable.map_md5,
    RatingsTable.rating,
)


class Rating(TypedDict):
    userid: int
    map_md5: str
    rating: int


async def create(userid: int, map_md5: str, rating: int) -> Rating:
    """Create a new rating."""
    insert_stmt = insert(RatingsTable).values(
        userid=userid,
        map_md5=map_md5,
        rating=rating,
    )
    await app.state.services.database.execute(insert_stmt)

    select_stmt = (
        select(*READ_PARAMS)
        .where(RatingsTable.userid == userid)
        .where(RatingsTable.map_md5 == map_md5)
    )
    _rating = await app.state.services.database.fetch_one(select_stmt)
    assert _rating is not None
    return cast(Rating, _rating)


async def fetch_many(
    userid: int | None = None,
    map_md5: str | None = None,
    page: int | None = 1,
    page_size: int | None = 50,
) -> list[Rating]:
    """Fetch multiple ratings, optionally with filter params and pagination."""
    select_stmt = select(*READ_PARAMS)
    if userid is not None:
        select_stmt = select_stmt.where(RatingsTable.userid == userid)
    if map_md5 is not None:
        select_stmt = select_stmt.where(RatingsTable.map_md5 == map_md5)

    if page is not None and page_size is not None:
        select_stmt = select_stmt.limit(page_size).offset((page - 1) * page_size)

    ratings = await app.state.services.database.fetch_all(select_stmt)
    return cast(list[Rating], ratings)


async def fetch_one(userid: int, map_md5: str) -> Rating | None:
    """Fetch a single rating for a given user and map."""
    select_stmt = (
        select(*READ_PARAMS)
        .where(RatingsTable.userid == userid)
        .where(RatingsTable.map_md5 == map_md5)
    )
    rating = await app.state.services.database.fetch_one(select_stmt)
    return cast(Rating | None, rating)
