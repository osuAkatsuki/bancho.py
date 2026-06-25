from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import func
from sqlalchemy import insert
from sqlalchemy import select

from app.adapters.database import Database
from app.adapters.database import MySQLRow
from app.repositories import Base


class FavouritesTable(Base):
    __tablename__ = "favourites"

    userid = Column("userid", Integer, nullable=False, primary_key=True)
    setid = Column("setid", Integer, nullable=False, primary_key=True)
    created_at = Column("created_at", Integer, nullable=False, server_default="0")


READ_PARAMS = (
    FavouritesTable.userid,
    FavouritesTable.setid,
    FavouritesTable.created_at,
)


@dataclass(frozen=True, slots=True)
class Favourite:
    userid: int
    setid: int
    created_at: int


class FavouritesRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def _serialize_favourite(self, favourite: Favourite) -> MySQLRow:
        return {
            "userid": favourite.userid,
            "setid": favourite.setid,
            "created_at": favourite.created_at,
        }

    def _deserialize_favourite(self, row: MySQLRow) -> Favourite:
        return Favourite(
            userid=row["userid"],
            setid=row["setid"],
            created_at=row["created_at"],
        )

    async def create(
        self,
        userid: int,
        setid: int,
    ) -> Favourite:
        """Create a new favourite mapset entry in the database."""
        insert_stmt = insert(FavouritesTable).values(
            userid=userid,
            setid=setid,
            created_at=func.unix_timestamp(),
        )
        await self._database.execute(insert_stmt)

        select_stmt = (
            select(*READ_PARAMS)
            .where(FavouritesTable.userid == userid)
            .where(FavouritesTable.setid == setid)
        )
        favourite = await self._database.fetch_one(select_stmt)

        assert favourite is not None
        return self._deserialize_favourite(favourite)

    async def fetch_all(self, userid: int) -> list[Favourite]:
        """Fetch all favourites from a player."""
        select_stmt = select(*READ_PARAMS).where(FavouritesTable.userid == userid)
        favourites = await self._database.fetch_all(select_stmt)
        return [self._deserialize_favourite(favourite) for favourite in favourites]

    async def fetch_one(self, userid: int, setid: int) -> Favourite | None:
        """Check if a mapset is already a favourite."""
        select_stmt = (
            select(*READ_PARAMS)
            .where(FavouritesTable.userid == userid)
            .where(FavouritesTable.setid == setid)
        )
        favourite = await self._database.fetch_one(select_stmt)
        return self._deserialize_favourite(favourite) if favourite is not None else None
