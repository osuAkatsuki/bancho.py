from __future__ import annotations

from typing import TypedDict
from typing import cast

from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import func
from sqlalchemy import insert
from sqlalchemy import select

from app.adapters.database import Database
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


class Favourite(TypedDict):
    userid: int
    setid: int
    created_at: int


class FavouritesRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

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
        return cast(Favourite, favourite)

    async def fetch_all(self, userid: int) -> list[Favourite]:
        """Fetch all favourites from a player."""
        select_stmt = select(*READ_PARAMS).where(FavouritesTable.userid == userid)
        favourites = await self._database.fetch_all(select_stmt)
        return cast(list[Favourite], favourites)

    async def fetch_one(self, userid: int, setid: int) -> Favourite | None:
        """Check if a mapset is already a favourite."""
        select_stmt = (
            select(*READ_PARAMS)
            .where(FavouritesTable.userid == userid)
            .where(FavouritesTable.setid == setid)
        )
        favourite = await self._database.fetch_one(select_stmt)
        return cast(Favourite | None, favourite)
