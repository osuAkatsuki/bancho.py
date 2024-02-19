from __future__ import annotations

from typing import TypedDict
from typing import cast

from sqlalchemy import Column
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import delete
from sqlalchemy import insert
from sqlalchemy import select

import app.state.services
from app.repositories import DIALECT
from app.repositories import Base


class TourneyPoolMapsTable(Base):
    __tablename__ = "tourney_pool_maps"

    map_id: Column = Column("map_id", Integer, nullable=False, primary_key=True)
    pool_id: Column = Column("pool_id", Integer, primary_key=True)
    mods: Column = Column("mods", Integer)
    slot: Column = Column("slot", Integer)

    __table_args__ = (
        Index("tourney_pool_maps_mods_slot_index", mods, slot),
        Index("tourney_pool_maps_tourney_pools_id_fk", pool_id),
    )


READ_PARAMS = (
    TourneyPoolMapsTable.map_id,
    TourneyPoolMapsTable.pool_id,
    TourneyPoolMapsTable.mods,
    TourneyPoolMapsTable.slot,
)


class TourneyPoolMap(TypedDict):
    map_id: int
    pool_id: int
    mods: int
    slot: int


async def create(map_id: int, pool_id: int, mods: int, slot: int) -> TourneyPoolMap:
    """Create a new map pool entry in the database."""
    insert_stmt = insert(TourneyPoolMapsTable).values(
        map_id=map_id,
        pool_id=pool_id,
        mods=mods,
        slot=slot,
    )
    compiled = insert_stmt.compile(dialect=DIALECT)
    await app.state.services.database.execute(str(compiled), compiled.params)

    select_stmt = (
        select(READ_PARAMS)
        .where(TourneyPoolMapsTable.map_id == map_id)
        .where(TourneyPoolMapsTable.pool_id == pool_id)
    )
    compiled = select_stmt.compile(dialect=DIALECT)
    tourney_pool_map = await app.state.services.database.fetch_one(
        str(compiled),
        compiled.params,
    )
    assert tourney_pool_map is not None
    return cast(TourneyPoolMap, dict(tourney_pool_map._mapping))


async def fetch_many(
    pool_id: int | None = None,
    mods: int | None = None,
    slot: int | None = None,
    page: int | None = 1,
    page_size: int | None = 50,
) -> list[TourneyPoolMap]:
    """Fetch a list of map pool entries from the database."""
    select_stmt = select(READ_PARAMS)
    if pool_id is not None:
        select_stmt = select_stmt.where(TourneyPoolMapsTable.pool_id == pool_id)
    if mods is not None:
        select_stmt = select_stmt.where(TourneyPoolMapsTable.mods == mods)
    if slot is not None:
        select_stmt = select_stmt.where(TourneyPoolMapsTable.slot == slot)
    if page and page_size:
        select_stmt = select_stmt.limit(page_size).offset((page - 1) * page_size)
    compiled = select_stmt.compile(dialect=DIALECT)
    tourney_pool_maps = await app.state.services.database.fetch_all(
        str(compiled),
        compiled.params,
    )
    return cast(
        list[TourneyPoolMap],
        [dict(tourney_pool_map._mapping) for tourney_pool_map in tourney_pool_maps],
    )


async def fetch_by_pool_and_pick(
    pool_id: int,
    mods: int,
    slot: int,
) -> TourneyPoolMap | None:
    """Fetch a map pool entry by pool and pick from the database."""
    select_stmt = (
        select(READ_PARAMS)
        .where(TourneyPoolMapsTable.pool_id == pool_id)
        .where(TourneyPoolMapsTable.mods == mods)
        .where(TourneyPoolMapsTable.slot == slot)
    )
    compiled = select_stmt.compile(dialect=DIALECT)
    tourney_pool_map = await app.state.services.database.fetch_one(
        str(compiled),
        compiled.params,
    )
    return (
        cast(TourneyPoolMap, dict(tourney_pool_map._mapping))
        if tourney_pool_map
        else None
    )


async def delete_map_from_pool(pool_id: int, map_id: int) -> TourneyPoolMap | None:
    """Delete a map pool entry from a given tourney pool from the database."""
    select_stmt = (
        select(READ_PARAMS)
        .where(TourneyPoolMapsTable.pool_id == pool_id)
        .where(TourneyPoolMapsTable.map_id == map_id)
    )
    compiled = select_stmt.compile(dialect=DIALECT)
    tourney_pool_map = await app.state.services.database.fetch_one(
        str(compiled),
        compiled.params,
    )
    if tourney_pool_map is None:
        return None

    delete_stmt = (
        delete(TourneyPoolMapsTable)
        .where(TourneyPoolMapsTable.pool_id == pool_id)
        .where(TourneyPoolMapsTable.map_id == map_id)
    )
    compiled = delete_stmt.compile(dialect=DIALECT)
    await app.state.services.database.execute(str(compiled), compiled.params)
    return cast(TourneyPoolMap, dict(tourney_pool_map._mapping))


async def delete_all_in_pool(pool_id: int) -> list[TourneyPoolMap]:
    """Delete all map pool entries from a given tourney pool from the database."""
    select_stmt = select(READ_PARAMS).where(TourneyPoolMapsTable.pool_id == pool_id)
    compiled = select_stmt.compile(dialect=DIALECT)
    tourney_pool_maps = await app.state.services.database.fetch_all(
        str(compiled),
        compiled.params,
    )
    if not tourney_pool_maps:
        return []

    delete_stmt = delete(TourneyPoolMapsTable).where(
        TourneyPoolMapsTable.pool_id == pool_id,
    )
    compiled = delete_stmt.compile(dialect=DIALECT)
    await app.state.services.database.execute(str(compiled), compiled.params)
    return cast(
        list[TourneyPoolMap],
        [dict(tourney_pool_map._mapping) for tourney_pool_map in tourney_pool_maps],
    )
