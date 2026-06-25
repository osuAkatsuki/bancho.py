from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.services.players as players
from app.constants.gamemodes import GameMode


class _FakeUsersRepository:
    def __init__(self) -> None:
        self.searches: list[str | None] = []
        self.fetch_one_calls: list[dict[str, object | None]] = []

    async def search_public(self, name: str | None = None) -> list[dict[str, object]]:
        self.searches.append(name)
        return [{"id": 3, "name": "cmyui"}]

    async def fetch_count(self) -> int:
        return 123

    async def fetch_one(
        self,
        id: int | None = None,
        name: str | None = None,
    ) -> dict[str, object] | None:
        self.fetch_one_calls.append({"id": id, "name": name})
        return {"id": id or 3, "name": name or "cmyui"}

    async def fetch_many(self, clan_id: int | None = None) -> list[dict[str, object]]:
        return [{"id": 4, "clan_id": clan_id}]


class _FakeStatsRepository:
    def __init__(self) -> None:
        self.leaderboard_calls: list[dict[str, object | None]] = []

    async def fetch_many(
        self,
        player_id: int | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> list[dict[str, object]]:
        return [{"id": player_id or 0, "mode": 0}]

    async def fetch_count(self, player_id: int | None = None) -> int:
        return 1 if player_id is not None else 0

    async def fetch_public_leaderboard(
        self,
        *,
        sort: str,
        mode: int,
        limit: int,
        offset: int,
        country: str | None,
    ) -> list[dict[str, object]]:
        self.leaderboard_calls.append(
            {
                "sort": sort,
                "mode": mode,
                "limit": limit,
                "offset": offset,
                "country": country,
            },
        )
        return [{"player_id": 3, "pp": 500}]


class _FakeOnlinePlayers:
    def __init__(self) -> None:
        self.player = SimpleNamespace(id=3, name="cmyui")
        self.unrestricted = {object(), object(), object()}
        self.get_calls: list[dict[str, object | None]] = []
        self.from_cache_or_sql_calls: list[dict[str, object | None]] = []

    def get(
        self,
        token: str | None = None,
        id: int | None = None,
        name: str | None = None,
    ) -> object | None:
        self.get_calls.append({"token": token, "id": id, "name": name})
        return self.player

    async def from_cache_or_sql(
        self,
        id: int | None = None,
        name: str | None = None,
    ) -> object | None:
        self.from_cache_or_sql_calls.append({"id": id, "name": name})
        return self.player


def _service() -> players.PlayersService:
    return players.PlayersService(
        users=_FakeUsersRepository(),
        stats=_FakeStatsRepository(),
        online_players=_FakeOnlinePlayers(),
    )


async def test_players_service_searches_public_players_and_counts_players() -> None:
    service = _service()

    assert await service.search_public_players("cm") == [{"id": 3, "name": "cmyui"}]
    assert service.fetch_online_player_count() == 2
    assert await service.fetch_total_player_count() == 123

    assert service.users.searches == ["cm"]


async def test_players_service_fetches_player_by_id_or_name() -> None:
    service = _service()

    assert await service.fetch_player_by_id_or_name(user_id=3, username=None) == {
        "id": 3,
        "name": "cmyui",
    }
    assert await service.fetch_player_by_id_or_name(user_id=None, username="peppy") == {
        "id": 3,
        "name": "peppy",
    }

    assert service.users.fetch_one_calls == [
        {"id": 3, "name": None},
        {"id": None, "name": "peppy"},
    ]


async def test_players_service_requires_player_lookup_key() -> None:
    service = _service()

    with pytest.raises(ValueError):
        await service.fetch_player_by_id_or_name(user_id=None, username=None)


async def test_players_service_fetches_online_and_cached_player_sessions() -> None:
    service = _service()

    assert service.fetch_online_player(user_id=None, username="cmyui") is (
        service.online_players.player
    )
    assert await service.fetch_player_session(user_id=3, username=None) is (
        service.online_players.player
    )
    assert await service.fetch_player_session(user_id=4, username="peppy") is (
        service.online_players.player
    )

    assert service.online_players.get_calls == [
        {"token": None, "id": None, "name": "cmyui"},
    ]
    assert service.online_players.from_cache_or_sql_calls == [
        {"id": 3, "name": None},
        {"id": 4, "name": None},
    ]


async def test_players_service_fetches_global_leaderboard() -> None:
    service = _service()

    rows = await service.fetch_global_leaderboard(
        sort="pp",
        mode=GameMode.VANILLA_OSU,
        limit=50,
        offset=10,
        country="ca",
    )

    assert rows == [{"player_id": 3, "pp": 500}]
    assert service.stats.leaderboard_calls == [
        {
            "sort": "pp",
            "mode": 0,
            "limit": 50,
            "offset": 10,
            "country": "ca",
        },
    ]
