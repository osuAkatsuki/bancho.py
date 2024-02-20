from __future__ import annotations

from typing import TypedDict
from typing import cast

from sqlalchemy import Column
from sqlalchemy import func
from sqlalchemy import insert
from sqlalchemy import select

import app.state.services
from app.repositories import Base


class FavouritesTable(Base):
    __tablename__ = "favourites"

    userid = Column("userid", nullable=False, primary_key=True)
    setid = Column("setid", nullable=False, primary_key=True)
    created_at = Column("integer", nullable=False, server_default="0")


READ_PARAMS = (
    FavouritesTable.userid,
    FavouritesTable.setid,
    FavouritesTable.created_at,
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
    insert_stmt = insert(FavouritesTable).values(
        userid=userid,
        setid=setid,
        created_at=func.unix_timestamp(),
    )
    await app.state.services.database.execute(insert_stmt)

    select_stmt = (
        select(*READ_PARAMS)
        .where(FavouritesTable.userid == userid)
        .where(FavouritesTable.setid == setid)
    )
    favourite = await app.state.services.database.fetch_one(select_stmt)

    assert favourite is not None
    return cast(Favourite, favourite)


async def fetch_all(userid: int) -> list[Favourite]:
    """Fetch all favourites from a player."""
    select_stmt = select(*READ_PARAMS).where(FavouritesTable.userid == userid)
    favourites = await app.state.services.database.fetch_all(select_stmt)
    return cast(list[Favourite], favourites)


async def fetch_one(userid: int, setid: int) -> Favourite | None:
    """Check if a mapset is already a favourite."""
    select_stmt = (
        select(*READ_PARAMS)
        .where(FavouritesTable.userid == userid)
        .where(FavouritesTable.setid == setid)
    )
    favourite = await app.state.services.database.fetch_one(select_stmt)
    return cast(Favourite | None, favourite)
