from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.repositories.favourites import FavouritesRepository


class AddFavouriteResult(StrEnum):
    ADDED = "added"
    ALREADY_FAVOURITED = "already_favourited"


@dataclass(frozen=True)
class FavouritesService:
    favourites: FavouritesRepository

    async def fetch_favourite_set_ids(self, player_id: int) -> list[int]:
        favourites = await self.favourites.fetch_all(userid=player_id)
        return [favourite.setid for favourite in favourites]

    async def add_favourite(
        self,
        *,
        player_id: int,
        map_set_id: int,
    ) -> AddFavouriteResult:
        if await self.favourites.fetch_one(player_id, map_set_id):
            return AddFavouriteResult.ALREADY_FAVOURITED

        await self.favourites.create(userid=player_id, setid=map_set_id)
        return AddFavouriteResult.ADDED

    async def remove_favourite(
        self,
        *,
        player_id: int,
        map_set_id: int,
    ) -> None:
        await self.favourites.delete(userid=player_id, setid=map_set_id)
