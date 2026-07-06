from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.adapters.database import Database
from app.repositories.tourney_pool_maps import TourneyPoolMap
from app.repositories.tourney_pool_maps import TourneyPoolMapsRepository
from app.repositories.tourney_pools import TourneyPool
from app.repositories.tourney_pools import TourneyPoolsRepository


class CreatePoolResultCode(StrEnum):
    CREATED = "created"
    NAME_TAKEN = "name_taken"


@dataclass(frozen=True)
class CreatePoolResult:
    code: CreatePoolResultCode
    pool: TourneyPool | None = None


class AddPoolMapResultCode(StrEnum):
    ADDED = "added"
    PICK_TAKEN = "pick_taken"
    MAP_ALREADY_IN_POOL = "map_already_in_pool"


@dataclass(frozen=True)
class AddPoolMapResult:
    code: AddPoolMapResultCode
    # the map currently occupying the pick, for PICK_TAKEN
    existing_map_id: int | None = None


@dataclass(frozen=True)
class TourneyPoolsService:
    tourney_pools: TourneyPoolsRepository
    tourney_pool_maps: TourneyPoolMapsRepository
    database: Database

    async def fetch_tourney_pool(self, pool_id: int) -> TourneyPool | None:
        return await self.tourney_pools.fetch_by_id(id=pool_id)

    async def fetch_tourney_pool_by_name(self, name: str) -> TourneyPool | None:
        return await self.tourney_pools.fetch_by_name(name)

    async def fetch_tourney_pools(self) -> list[TourneyPool]:
        return await self.tourney_pools.fetch_many(page=None, page_size=None)

    async def fetch_tourney_pool_maps(
        self,
        pool_id: int,
    ) -> list[TourneyPoolMap]:
        return await self.tourney_pool_maps.fetch_many(pool_id=pool_id)

    async def fetch_pool_map_pick(
        self,
        *,
        pool_id: int,
        mods: int,
        slot: int,
    ) -> TourneyPoolMap | None:
        return await self.tourney_pool_maps.fetch_by_pool_and_pick(
            pool_id=pool_id,
            mods=mods,
            slot=slot,
        )

    async def create_pool(self, *, name: str, created_by: int) -> CreatePoolResult:
        if await self.tourney_pools.fetch_by_name(name) is not None:
            return CreatePoolResult(code=CreatePoolResultCode.NAME_TAKEN)

        pool = await self.tourney_pools.create(name=name, created_by=created_by)
        return CreatePoolResult(code=CreatePoolResultCode.CREATED, pool=pool)

    async def delete_pool(self, pool_id: int) -> TourneyPool | None:
        pool = await self.tourney_pools.fetch_by_id(id=pool_id)
        if pool is None:
            return None

        async with self.database.transaction():
            await self.tourney_pools.delete_by_id(pool.id)
            await self.tourney_pool_maps.delete_all_in_pool(pool_id=pool.id)

        return pool

    async def add_map_to_pool(
        self,
        *,
        pool_id: int,
        map_id: int,
        mods: int,
        slot: int,
    ) -> AddPoolMapResult:
        pool_maps = await self.tourney_pool_maps.fetch_many(pool_id=pool_id)
        for pool_map in pool_maps:
            if mods == pool_map.mods and slot == pool_map.slot:
                return AddPoolMapResult(
                    code=AddPoolMapResultCode.PICK_TAKEN,
                    existing_map_id=pool_map.map_id,
                )
            if pool_map.map_id == map_id:
                return AddPoolMapResult(code=AddPoolMapResultCode.MAP_ALREADY_IN_POOL)

        await self.tourney_pool_maps.create(
            map_id=map_id,
            pool_id=pool_id,
            mods=mods,
            slot=slot,
        )
        return AddPoolMapResult(code=AddPoolMapResultCode.ADDED)

    async def remove_map_from_pool(
        self,
        *,
        pool_id: int,
        mods: int,
        slot: int,
    ) -> TourneyPoolMap | None:
        map_pick = await self.tourney_pool_maps.fetch_by_pool_and_pick(
            pool_id=pool_id,
            mods=mods,
            slot=slot,
        )
        if map_pick is None:
            return None

        await self.tourney_pool_maps.delete_map_from_pool(
            map_pick.pool_id,
            map_pick.map_id,
        )
        return map_pick
