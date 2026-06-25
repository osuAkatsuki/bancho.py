from __future__ import annotations

from dataclasses import dataclass

from app.repositories.clans import Clan
from app.repositories.clans import ClansRepository


@dataclass(frozen=True)
class ClansListing:
    clans: list[Clan]
    total_clans: int


@dataclass(frozen=True)
class ClansService:
    clans: ClansRepository

    async def fetch_clans(self, *, page: int, page_size: int) -> ClansListing:
        clans = await self.clans.fetch_many(page=page, page_size=page_size)
        total_clans = await self.clans.fetch_count()

        return ClansListing(clans=clans, total_clans=total_clans)

    async def fetch_clan(self, clan_id: int) -> Clan | None:
        return await self.clans.fetch_one(id=clan_id)
