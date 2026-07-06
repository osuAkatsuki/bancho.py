from __future__ import annotations

from datetime import datetime
from typing import Any

import app.services.tourney_pools as tourney_pools
from app.repositories.tourney_pool_maps import TourneyPoolMap
from app.repositories.tourney_pools import TourneyPool


def _pool(id: int = 1, name: str = "OWC2024", created_by: int = 3) -> TourneyPool:
    return TourneyPool(
        id=id,
        name=name,
        created_at=datetime(2024, 1, 1),
        created_by=created_by,
    )


def _pool_map(
    map_id: int,
    *,
    pool_id: int = 1,
    mods: int = 0,
    slot: int = 1,
) -> TourneyPoolMap:
    return TourneyPoolMap(map_id=map_id, pool_id=pool_id, mods=mods, slot=slot)


class _FakeTourneyPoolsRepository:
    def __init__(self, pools: list[TourneyPool] | None = None) -> None:
        self.pools = {pool.id: pool for pool in (pools or [])}

    async def create(self, name: str, created_by: int) -> TourneyPool:
        pool = TourneyPool(
            id=max(self.pools, default=0) + 1,
            name=name,
            created_at=datetime(2024, 1, 1),
            created_by=created_by,
        )
        self.pools[pool.id] = pool
        return pool

    async def fetch_by_id(self, id: int) -> TourneyPool | None:
        return self.pools.get(id)

    async def fetch_by_name(self, name: str) -> TourneyPool | None:
        for pool in self.pools.values():
            if pool.name == name:
                return pool
        return None

    async def fetch_many(
        self,
        page: int | None = None,
        page_size: int | None = None,
    ) -> list[TourneyPool]:
        return list(self.pools.values())

    async def delete_by_id(self, id: int) -> TourneyPool | None:
        return self.pools.pop(id, None)


class _FakeTourneyPoolMapsRepository:
    def __init__(self, pool_maps: list[TourneyPoolMap] | None = None) -> None:
        self.pool_maps = list(pool_maps or [])

    async def create(
        self,
        map_id: int,
        pool_id: int,
        mods: int,
        slot: int,
    ) -> TourneyPoolMap:
        pool_map = TourneyPoolMap(
            map_id=map_id,
            pool_id=pool_id,
            mods=mods,
            slot=slot,
        )
        self.pool_maps.append(pool_map)
        return pool_map

    async def fetch_many(self, *, pool_id: int) -> list[TourneyPoolMap]:
        return [pool_map for pool_map in self.pool_maps if pool_map.pool_id == pool_id]

    async def fetch_by_pool_and_pick(
        self,
        *,
        pool_id: int,
        mods: int,
        slot: int,
    ) -> TourneyPoolMap | None:
        for pool_map in self.pool_maps:
            if (
                pool_map.pool_id == pool_id
                and pool_map.mods == mods
                and pool_map.slot == slot
            ):
                return pool_map
        return None

    async def delete_map_from_pool(
        self,
        pool_id: int,
        map_id: int,
    ) -> TourneyPoolMap | None:
        for pool_map in self.pool_maps:
            if pool_map.pool_id == pool_id and pool_map.map_id == map_id:
                self.pool_maps.remove(pool_map)
                return pool_map
        return None

    async def delete_all_in_pool(self, pool_id: int) -> list[TourneyPoolMap]:
        deleted = [
            pool_map for pool_map in self.pool_maps if pool_map.pool_id == pool_id
        ]
        self.pool_maps = [
            pool_map for pool_map in self.pool_maps if pool_map.pool_id != pool_id
        ]
        return deleted


class _FakeTransaction:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    async def __aenter__(self) -> None:
        self.calls.append("transaction_enter")

    async def __aexit__(self, *args: Any) -> None:
        self.calls.append("transaction_exit")


class _FakeDatabase:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def transaction(self) -> _FakeTransaction:
        return _FakeTransaction(self.calls)


def _service(
    *,
    pools: list[TourneyPool] | None = None,
    pool_maps: list[TourneyPoolMap] | None = None,
) -> tuple[
    tourney_pools.TourneyPoolsService,
    _FakeTourneyPoolsRepository,
    _FakeTourneyPoolMapsRepository,
    _FakeDatabase,
]:
    pools_repo = _FakeTourneyPoolsRepository(pools)
    pool_maps_repo = _FakeTourneyPoolMapsRepository(pool_maps)
    database = _FakeDatabase()
    service = tourney_pools.TourneyPoolsService(
        tourney_pools=pools_repo,
        tourney_pool_maps=pool_maps_repo,
        database=database,
    )
    return service, pools_repo, pool_maps_repo, database


async def test_create_pool_persists_the_pool() -> None:
    service, pools_repo, *_ = _service()

    result = await service.create_pool(name="OWC2024", created_by=3)

    assert result.code is tourney_pools.CreatePoolResultCode.CREATED
    assert result.pool is not None
    assert pools_repo.pools[result.pool.id].name == "OWC2024"


async def test_create_pool_rejects_taken_names() -> None:
    service, *_ = _service(pools=[_pool()])

    result = await service.create_pool(name="OWC2024", created_by=3)

    assert result.code is tourney_pools.CreatePoolResultCode.NAME_TAKEN


async def test_delete_pool_removes_the_pool_and_its_maps_atomically() -> None:
    service, pools_repo, pool_maps_repo, database = _service(
        pools=[_pool()],
        pool_maps=[
            _pool_map(101, slot=1),
            _pool_map(102, slot=2),
            _pool_map(201, pool_id=2, slot=1),  # another pool's map survives
        ],
    )

    deleted = await service.delete_pool(1)

    assert deleted is not None
    assert pools_repo.pools == {}
    assert [pool_map.map_id for pool_map in pool_maps_repo.pool_maps] == [201]
    # both deletes happen within a single transaction
    assert database.calls == ["transaction_enter", "transaction_exit"]


async def test_delete_pool_returns_none_for_missing_pools() -> None:
    service, *_ = _service()
    assert await service.delete_pool(42) is None


async def test_add_map_to_pool_persists_the_pick() -> None:
    service, _, pool_maps_repo, _ = _service(pools=[_pool()])

    result = await service.add_map_to_pool(pool_id=1, map_id=101, mods=8, slot=2)

    assert result.code is tourney_pools.AddPoolMapResultCode.ADDED
    assert [pm.map_id for pm in pool_maps_repo.pool_maps] == [101]


async def test_add_map_to_pool_rejects_taken_picks() -> None:
    service, *_ = _service(
        pools=[_pool()],
        pool_maps=[_pool_map(101, mods=8, slot=2)],
    )

    result = await service.add_map_to_pool(pool_id=1, map_id=102, mods=8, slot=2)

    assert result.code is tourney_pools.AddPoolMapResultCode.PICK_TAKEN
    assert result.existing_map_id == 101


async def test_add_map_to_pool_rejects_duplicate_maps() -> None:
    service, *_ = _service(
        pools=[_pool()],
        pool_maps=[_pool_map(101, mods=8, slot=2)],
    )

    result = await service.add_map_to_pool(pool_id=1, map_id=101, mods=0, slot=3)

    assert result.code is tourney_pools.AddPoolMapResultCode.MAP_ALREADY_IN_POOL


async def test_remove_map_from_pool_deletes_the_pick() -> None:
    service, _, pool_maps_repo, _ = _service(
        pools=[_pool()],
        pool_maps=[_pool_map(101, mods=8, slot=2)],
    )

    removed = await service.remove_map_from_pool(pool_id=1, mods=8, slot=2)

    assert removed is not None
    assert removed.map_id == 101
    assert pool_maps_repo.pool_maps == []


async def test_remove_map_from_pool_returns_none_for_missing_picks() -> None:
    service, *_ = _service(pools=[_pool()])
    assert await service.remove_map_from_pool(pool_id=1, mods=8, slot=2) is None


async def test_pool_reads() -> None:
    service, *_ = _service(
        pools=[_pool(), _pool(id=2, name="Corsace")],
        pool_maps=[_pool_map(101, mods=8, slot=2)],
    )

    assert await service.fetch_tourney_pool(1) is not None
    assert await service.fetch_tourney_pool_by_name("Corsace") is not None
    assert await service.fetch_tourney_pool_by_name("missing") is None
    assert len(await service.fetch_tourney_pools()) == 2
    assert len(await service.fetch_tourney_pool_maps(pool_id=1)) == 1

    pick = await service.fetch_pool_map_pick(pool_id=1, mods=8, slot=2)
    assert pick is not None and pick.map_id == 101
