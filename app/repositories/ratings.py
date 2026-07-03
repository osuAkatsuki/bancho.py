from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import func
from sqlalchemy import insert
from sqlalchemy import select
from sqlalchemy.dialects.mysql import TINYINT

from app.adapters.database import Database
from app.adapters.database import MySQLRow
from app.repositories import Base


class RatingsTable(Base):
    __tablename__ = "ratings"

    userid = Column("userid", Integer, nullable=False, primary_key=True)
    map_md5 = Column("map_md5", String(32), nullable=False, primary_key=True)
    rating = Column("rating", TINYINT(2), nullable=False)


READ_PARAMS = (
    RatingsTable.userid,
    RatingsTable.map_md5,
    RatingsTable.rating,
)


@dataclass(frozen=True, slots=True)
class Rating:
    userid: int
    map_md5: str
    rating: int


@dataclass(frozen=True, slots=True)
class MapRatingStats:
    average: float | None
    count: int


class RatingsRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def _deserialize_rating(self, row: MySQLRow) -> Rating:
        return Rating(
            userid=row["userid"],
            map_md5=row["map_md5"],
            rating=row["rating"],
        )

    async def create(self, userid: int, map_md5: str, rating: int) -> Rating:
        """Create a new rating."""
        insert_stmt = insert(RatingsTable).values(
            userid=userid,
            map_md5=map_md5,
            rating=rating,
        )
        await self._database.execute(insert_stmt)

        select_stmt = (
            select(*READ_PARAMS)
            .where(RatingsTable.userid == userid)
            .where(RatingsTable.map_md5 == map_md5)
        )
        _rating = await self._database.fetch_one(select_stmt)
        assert _rating is not None
        return self._deserialize_rating(_rating)

    async def fetch_many(
        self,
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

        ratings = await self._database.fetch_all(select_stmt)
        return [self._deserialize_rating(rating) for rating in ratings]

    async def fetch_one(self, userid: int, map_md5: str) -> Rating | None:
        """Fetch a single rating for a given user and map."""
        select_stmt = (
            select(*READ_PARAMS)
            .where(RatingsTable.userid == userid)
            .where(RatingsTable.map_md5 == map_md5)
        )
        rating = await self._database.fetch_one(select_stmt)
        return self._deserialize_rating(rating) if rating is not None else None

    async def fetch_map_rating_stats(self, map_md5: str) -> MapRatingStats:
        """Fetch the average rating and rating count for a given map."""
        select_stmt = select(
            func.avg(RatingsTable.rating).label("average"),
            func.count().label("count"),
        ).where(RatingsTable.map_md5 == map_md5)

        stats = await self._database.fetch_one(select_stmt)
        assert stats is not None
        return MapRatingStats(
            average=float(stats["average"]) if stats["average"] is not None else None,
            count=stats["count"],
        )
