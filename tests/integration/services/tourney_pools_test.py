from __future__ import annotations

import secrets

import pytest

import app.state.services
from app.constants.mods import Mods
from app.constants.privileges import Privileges
from app.repositories.tourney_pool_maps import TourneyPoolMap
from app.repositories.tourney_pool_maps import TourneyPoolMapsRepository
from app.repositories.tourney_pools import TourneyPoolsRepository
from app.services.tourney_pools import AddPoolMapResultCode
from app.services.tourney_pools import CreatePoolResultCode
from app.services.tourney_pools import TourneyPoolsService
from tests import factories

VISIBLE_PRIV = int(Privileges.UNRESTRICTED | Privileges.VERIFIED)


class _FailingPoolMapsRepository(TourneyPoolMapsRepository):
    async def delete_all_in_pool(self, pool_id: int) -> list[TourneyPoolMap]:
        raise RuntimeError("fail after pool delete")


def _tourney_pools_service(
    *,
    pool_maps: TourneyPoolMapsRepository | None = None,
) -> TourneyPoolsService:
    database = app.state.services.database
    return TourneyPoolsService(
        tourney_pools=TourneyPoolsRepository(database),
        tourney_pool_maps=pool_maps or TourneyPoolMapsRepository(database),
        database=database,
    )


async def test_tourney_pool_lifecycle_persists_and_deletes_pool_maps() -> None:
    creator = await factories.create_user(priv=VISIBLE_PRIV)
    first_map = await factories.create_map()
    second_map = await factories.create_map()
    service = _tourney_pools_service()

    created = await service.create_pool(
        name=f"Pool {secrets.token_hex(3)}",
        created_by=creator.id,
    )

    assert created.code is CreatePoolResultCode.CREATED
    assert created.pool is not None
    pool = created.pool
    first_added = await service.add_map_to_pool(
        pool_id=pool.id,
        map_id=first_map.id,
        mods=int(Mods.HIDDEN),
        slot=1,
    )
    second_added = await service.add_map_to_pool(
        pool_id=pool.id,
        map_id=second_map.id,
        mods=int(Mods.HARDROCK),
        slot=1,
    )
    assert first_added.code is AddPoolMapResultCode.ADDED
    assert second_added.code is AddPoolMapResultCode.ADDED
    assert {
        pool_map.map_id for pool_map in await service.fetch_tourney_pool_maps(pool.id)
    } == {
        first_map.id,
        second_map.id,
    }

    removed = await service.remove_map_from_pool(
        pool_id=pool.id,
        mods=int(Mods.HIDDEN),
        slot=1,
    )

    assert removed is not None
    assert removed.map_id == first_map.id
    assert [
        pool_map.map_id for pool_map in await service.fetch_tourney_pool_maps(pool.id)
    ] == [second_map.id]

    deleted = await service.delete_pool(pool.id)

    assert deleted == pool
    assert await service.fetch_tourney_pool(pool.id) is None
    assert await service.fetch_tourney_pool_maps(pool.id) == []


async def test_delete_pool_rolls_back_when_map_cleanup_fails() -> None:
    creator = await factories.create_user(priv=VISIBLE_PRIV)
    beatmap = await factories.create_map()
    database = app.state.services.database
    service = _tourney_pools_service()
    created = await service.create_pool(
        name=f"Pool {secrets.token_hex(3)}",
        created_by=creator.id,
    )
    assert created.pool is not None
    pool = created.pool
    added = await service.add_map_to_pool(
        pool_id=pool.id,
        map_id=beatmap.id,
        mods=int(Mods.NOMOD),
        slot=1,
    )
    assert added.code is AddPoolMapResultCode.ADDED
    failing_service = _tourney_pools_service(
        pool_maps=_FailingPoolMapsRepository(database),
    )

    with pytest.raises(RuntimeError, match="fail after pool delete"):
        await failing_service.delete_pool(pool.id)

    assert await service.fetch_tourney_pool(pool.id) == pool
    persisted_maps = await service.fetch_tourney_pool_maps(pool.id)
    assert len(persisted_maps) == 1
    assert persisted_maps[0].map_id == beatmap.id
