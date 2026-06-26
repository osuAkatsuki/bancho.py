from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Column
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import delete
from sqlalchemy import insert
from sqlalchemy import select

from app.adapters.database import Database
from app.adapters.database import MySQLRow
from app.repositories import Base


class TourneyPoolMapsTable(Base):
    __tablename__ = "tourney_pool_maps"

    map_id = Column("map_id", Integer, nullable=False, primary_key=True)
    pool_id = Column("pool_id", Integer, nullable=False, primary_key=True)
    mods = Column("mods", Integer, nullable=False)
    slot = Column("slot", Integer, nullable=False)

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


@dataclass(frozen=True, slots=True)
class TourneyPoolMap:
    map_id: int
    pool_id: int
    mods: int
    slot: int


class TourneyPoolMapsRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def _deserialize_tourney_pool_map(self, row: MySQLRow) -> TourneyPoolMap:
        return TourneyPoolMap(
            map_id=row["map_id"],
            pool_id=row["pool_id"],
            mods=row["mods"],
            slot=row["slot"],
        )

    async def create(
        self,
        map_id: int,
        pool_id: int,
        mods: int,
        slot: int,
    ) -> TourneyPoolMap:
        """Create a new map pool entry in the database."""
        insert_stmt = insert(TourneyPoolMapsTable).values(
            map_id=map_id,
            pool_id=pool_id,
            mods=mods,
            slot=slot,
        )
        await self._database.execute(insert_stmt)

        select_stmt = (
            select(*READ_PARAMS)
            .where(TourneyPoolMapsTable.map_id == map_id)
            .where(TourneyPoolMapsTable.pool_id == pool_id)
        )
        tourney_pool_map = await self._database.fetch_one(select_stmt)
        assert tourney_pool_map is not None
        return self._deserialize_tourney_pool_map(tourney_pool_map)

    async def fetch_many(
        self,
        pool_id: int | None = None,
        mods: int | None = None,
        slot: int | None = None,
        page: int | None = 1,
        page_size: int | None = 50,
    ) -> list[TourneyPoolMap]:
        """Fetch a list of map pool entries from the database."""
        select_stmt = select(*READ_PARAMS)
        if pool_id is not None:
            select_stmt = select_stmt.where(TourneyPoolMapsTable.pool_id == pool_id)
        if mods is not None:
            select_stmt = select_stmt.where(TourneyPoolMapsTable.mods == mods)
        if slot is not None:
            select_stmt = select_stmt.where(TourneyPoolMapsTable.slot == slot)
        if page and page_size:
            select_stmt = select_stmt.limit(page_size).offset((page - 1) * page_size)

        tourney_pool_maps = await self._database.fetch_all(select_stmt)
        return [
            self._deserialize_tourney_pool_map(tourney_pool_map)
            for tourney_pool_map in tourney_pool_maps
        ]

    async def fetch_by_pool_and_pick(
        self,
        pool_id: int,
        mods: int,
        slot: int,
    ) -> TourneyPoolMap | None:
        """Fetch a map pool entry by pool and pick from the database."""
        select_stmt = (
            select(*READ_PARAMS)
            .where(TourneyPoolMapsTable.pool_id == pool_id)
            .where(TourneyPoolMapsTable.mods == mods)
            .where(TourneyPoolMapsTable.slot == slot)
        )
        tourney_pool_map = await self._database.fetch_one(select_stmt)
        return (
            self._deserialize_tourney_pool_map(tourney_pool_map)
            if tourney_pool_map is not None
            else None
        )

    async def delete_map_from_pool(
        self,
        pool_id: int,
        map_id: int,
    ) -> TourneyPoolMap | None:
        """Delete a map pool entry from a given tourney pool from the database."""
        select_stmt = (
            select(*READ_PARAMS)
            .where(TourneyPoolMapsTable.pool_id == pool_id)
            .where(TourneyPoolMapsTable.map_id == map_id)
        )

        tourney_pool_map = await self._database.fetch_one(select_stmt)
        if tourney_pool_map is None:
            return None

        delete_stmt = (
            delete(TourneyPoolMapsTable)
            .where(TourneyPoolMapsTable.pool_id == pool_id)
            .where(TourneyPoolMapsTable.map_id == map_id)
        )

        await self._database.execute(delete_stmt)
        return self._deserialize_tourney_pool_map(tourney_pool_map)

    async def delete_all_in_pool(self, pool_id: int) -> list[TourneyPoolMap]:
        """Delete all map pool entries from a given tourney pool from the database."""
        select_stmt = select(*READ_PARAMS).where(
            TourneyPoolMapsTable.pool_id == pool_id,
        )
        tourney_pool_maps = await self._database.fetch_all(select_stmt)
        if not tourney_pool_maps:
            return []

        delete_stmt = delete(TourneyPoolMapsTable).where(
            TourneyPoolMapsTable.pool_id == pool_id,
        )
        await self._database.execute(delete_stmt)
        return [
            self._deserialize_tourney_pool_map(tourney_pool_map)
            for tourney_pool_map in tourney_pool_maps
        ]
