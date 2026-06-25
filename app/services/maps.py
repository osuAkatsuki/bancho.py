from __future__ import annotations

from dataclasses import dataclass

from app.repositories.maps import Map
from app.repositories.maps import MapsRepository


@dataclass(frozen=True)
class MapsListing:
    maps: list[Map]
    total_maps: int


@dataclass(frozen=True)
class MapsService:
    maps: MapsRepository

    async def fetch_maps(
        self,
        *,
        set_id: int | None,
        server: str | None,
        status: int | None,
        artist: str | None,
        creator: str | None,
        filename: str | None,
        mode: int | None,
        frozen: bool | None,
        page: int,
        page_size: int,
    ) -> MapsListing:
        maps = await self.maps.fetch_many(
            server=server,
            set_id=set_id,
            status=status,
            artist=artist,
            creator=creator,
            filename=filename,
            mode=mode,
            frozen=frozen,
            page=page,
            page_size=page_size,
        )
        total_maps = await self.maps.fetch_count(
            server=server,
            set_id=set_id,
            status=status,
            artist=artist,
            creator=creator,
            filename=filename,
            mode=mode,
            frozen=frozen,
        )

        return MapsListing(maps=maps, total_maps=total_maps)

    async def fetch_map(self, map_id: int) -> Map | None:
        return await self.maps.fetch_one(id=map_id)
