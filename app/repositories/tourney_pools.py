from __future__ import annotations

from datetime import datetime
from typing import TypedDict
from typing import cast

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import delete
from sqlalchemy import func
from sqlalchemy import insert
from sqlalchemy import select
from sqlalchemy.dialects.mysql import VARCHAR

import app.state.services
from app.repositories import Base


class TourneyPoolsTable(Base):
    __tablename__ = "tourney_pools"

    id = Column("id", Integer, nullable=False, primary_key=True, autoincrement=True)
    name = Column("name", VARCHAR(length=16), nullable=False)
    created_at = Column("created_at", DateTime, nullable=False)
    created_by = Column("created_by", Integer, nullable=False)

    __table_args__ = (Index("tourney_pools_users_id_fk", created_by),)


class TourneyPool(TypedDict):
    id: int
    name: str
    created_at: datetime
    created_by: int


READ_PARAMS = (
    TourneyPoolsTable.id,
    TourneyPoolsTable.name,
    TourneyPoolsTable.created_at,
    TourneyPoolsTable.created_by,
)


async def create(name: str, created_by: int) -> TourneyPool:
    """Create a new tourney pool entry in the database."""
    insert_stmt = insert(TourneyPoolsTable).values(
        name=name,
        created_at=func.now(),
        created_by=created_by,
    )
    rec_id = await app.state.services.database.execute(insert_stmt)

    select_stmt = select(*READ_PARAMS).where(TourneyPoolsTable.id == rec_id)
    tourney_pool = await app.state.services.database.fetch_one(select_stmt)
    assert tourney_pool is not None
    return cast(TourneyPool, tourney_pool)


async def fetch_many(
    id: int | None = None,
    created_by: int | None = None,
    page: int | None = 1,
    page_size: int | None = 50,
) -> list[TourneyPool]:
    """Fetch many tourney pools from the database."""
    select_stmt = select(*READ_PARAMS)
    if id is not None:
        select_stmt = select_stmt.where(TourneyPoolsTable.id == id)
    if created_by is not None:
        select_stmt = select_stmt.where(TourneyPoolsTable.created_by == created_by)
    if page and page_size:
        select_stmt = select_stmt.limit(page_size).offset((page - 1) * page_size)

    tourney_pools = await app.state.services.database.fetch_all(select_stmt)
    return cast(list[TourneyPool], tourney_pools)


async def fetch_by_name(name: str) -> TourneyPool | None:
    """Fetch a tourney pool by name from the database."""
    select_stmt = select(*READ_PARAMS).where(TourneyPoolsTable.name == name)
    tourney_pool = await app.state.services.database.fetch_one(select_stmt)
    return cast(TourneyPool | None, tourney_pool)


async def fetch_by_id(id: int) -> TourneyPool | None:
    """Fetch a tourney pool by id from the database."""
    select_stmt = select(*READ_PARAMS).where(TourneyPoolsTable.id == id)
    tourney_pool = await app.state.services.database.fetch_one(select_stmt)
    return cast(TourneyPool | None, tourney_pool)


async def delete_by_id(id: int) -> TourneyPool | None:
    """Delete a tourney pool by id from the database."""
    select_stmt = select(*READ_PARAMS).where(TourneyPoolsTable.id == id)
    tourney_pool = await app.state.services.database.fetch_one(select_stmt)
    if tourney_pool is None:
        return None

    delete_stmt = delete(TourneyPoolsTable).where(TourneyPoolsTable.id == id)
    await app.state.services.database.execute(delete_stmt)
    return cast(TourneyPool, tourney_pool)
