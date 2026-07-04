from __future__ import annotations

import app.services.favourites as favourites


class _FakeFavouritesRepository:
    def __init__(self, *, existing: bool = False) -> None:
        self.existing = existing
        self.created_favourites: list[dict[str, int]] = []
        self.deleted_favourites: list[dict[str, int]] = []

    async def fetch_one(self, player_id: int, map_set_id: int) -> object | None:
        return object() if self.existing else None

    async def create(self, *, userid: int, setid: int) -> None:
        self.created_favourites.append({"userid": userid, "setid": setid})

    async def delete(self, *, userid: int, setid: int) -> None:
        self.deleted_favourites.append({"userid": userid, "setid": setid})


async def test_favourites_service_adds_missing_favourite() -> None:
    favourites_repo = _FakeFavouritesRepository()
    service = favourites.FavouritesService(favourites=favourites_repo)

    result = await service.add_favourite(player_id=1, map_set_id=2)

    assert result is favourites.AddFavouriteResult.ADDED
    assert favourites_repo.created_favourites == [{"userid": 1, "setid": 2}]


async def test_favourites_service_does_not_duplicate_existing_favourite() -> None:
    favourites_repo = _FakeFavouritesRepository(existing=True)
    service = favourites.FavouritesService(favourites=favourites_repo)

    result = await service.add_favourite(player_id=1, map_set_id=2)

    assert result is favourites.AddFavouriteResult.ALREADY_FAVOURITED
    assert favourites_repo.created_favourites == []


async def test_favourites_service_removes_favourite() -> None:
    favourites_repo = _FakeFavouritesRepository(existing=True)
    service = favourites.FavouritesService(favourites=favourites_repo)

    await service.remove_favourite(player_id=1, map_set_id=2)

    assert favourites_repo.deleted_favourites == [{"userid": 1, "setid": 2}]
