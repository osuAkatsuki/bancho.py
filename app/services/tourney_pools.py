from __future__ import annotations

from dataclasses import dataclass

from app.repositories.tourney_pool_maps import TourneyPoolMap
from app.repositories.tourney_pool_maps import TourneyPoolMapsRepository
from app.repositories.tourney_pools import TourneyPool
from app.repositories.tourney_pools import TourneyPoolsRepository


@dataclass(frozen=True)
class TourneyPoolsService:
    tourney_pools: TourneyPoolsRepository
    tourney_pool_maps: TourneyPoolMapsRepository

    async def fetch_tourney_pool(self, pool_id: int) -> TourneyPool | None:
        return await self.tourney_pools.fetch_by_id(id=pool_id)

    async def fetch_tourney_pool_maps(
        self,
        pool_id: int,
    ) -> list[TourneyPoolMap]:
        return await self.tourney_pool_maps.fetch_many(pool_id=pool_id)
