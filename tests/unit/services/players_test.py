from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.services.players as players
from app.constants.privileges import Privileges


def _stat(mode: int = 0) -> SimpleNamespace:
    return SimpleNamespace(
        id=3,
        mode=mode,
        tscore=1000,
        rscore=800,
        pp=500,
        plays=25,
        playtime=3600,
        acc=98.76,
        max_combo=512,
        total_hits=1234,
        replay_views=10,
        xh_count=1,
        x_count=2,
        sh_count=3,
        s_count=4,
        a_count=5,
    )


class _FakeUsersRepository:
    def __init__(self) -> None:
        self.searches: list[dict[str, object | None]] = []
        self.fetch_one_calls: list[dict[str, object | None]] = []

    async def search_public(
        self,
        name: str | None = None,
        include_hidden: bool = False,
        always_visible_id: int | None = None,
    ) -> list[dict[str, object]]:
        self.searches.append(
            {
                "name": name,
                "include_hidden": include_hidden,
                "always_visible_id": always_visible_id,
            },
        )
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
    async def fetch_one(self, player_id: int, mode: int) -> SimpleNamespace | None:
        return _stat(mode) if mode in (0, 4) else None

    async def fetch_many(
        self,
        player_id: int | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> list[SimpleNamespace]:
        return [_stat(0), _stat(4)]

    async def fetch_count(self, player_id: int | None = None) -> int:
        return 2 if player_id is not None else 0


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


class _FakePlayerLeaderboardsService:
    def __init__(self, ranks: players.ModeRanks | None = None) -> None:
        self.ranks = (
            ranks
            if ranks is not None
            else players.ModeRanks(global_rank=None, country_rank=None)
        )
        self.calls: list[dict[str, object]] = []

    async def fetch_player_mode_ranks(
        self,
        *,
        player_id: int,
        mode: int,
        country: str,
    ) -> players.ModeRanks:
        self.calls.append({"player_id": player_id, "mode": mode, "country": country})
        return self.ranks


def _service(
    player_leaderboards: _FakePlayerLeaderboardsService | None = None,
) -> players.PlayersService:
    if player_leaderboards is None:
        player_leaderboards = _FakePlayerLeaderboardsService()

    return players.PlayersService(
        users=_FakeUsersRepository(),
        stats=_FakeStatsRepository(),
        online_players=_FakeOnlinePlayers(),
        player_leaderboards=player_leaderboards,
    )


async def test_players_service_searches_public_players_and_counts_players() -> None:
    service = _service()

    assert await service.search_players("cm", viewer=None) == [
        {"id": 3, "name": "cmyui"},
    ]
    assert service.fetch_online_player_count() == 2
    assert await service.fetch_total_player_count() == 123

    assert service.users.searches == [
        {"name": "cm", "include_hidden": False, "always_visible_id": None},
    ]


async def test_players_service_search_visibility_rules() -> None:
    service = _service()

    # regular signed-in players can always find themselves
    regular = SimpleNamespace(id=5, priv=int(Privileges.UNRESTRICTED))
    await service.search_players("cm", viewer=regular)

    # staff see hidden players
    staff = SimpleNamespace(
        id=6,
        priv=int(Privileges.UNRESTRICTED | Privileges.ADMINISTRATOR),
    )
    await service.search_players("cm", viewer=staff)

    assert service.users.searches == [
        {"name": "cm", "include_hidden": False, "always_visible_id": 5},
        {"name": "cm", "include_hidden": True, "always_visible_id": 6},
    ]


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


async def test_players_service_composes_mode_stats_with_ranks() -> None:
    player_leaderboards = _FakePlayerLeaderboardsService(
        ranks=players.ModeRanks(global_rank=4, country_rank=2),
    )
    service = _service(player_leaderboards=player_leaderboards)

    ranked = await service.fetch_player_mode_stats_with_ranks(
        player_id=3,
        mode=0,
        country="ca",
    )

    assert ranked is not None
    assert ranked.pp == 500
    assert ranked.rank == 4
    assert ranked.country_rank == 2
    assert player_leaderboards.calls == [
        {"player_id": 3, "mode": 0, "country": "ca"},
    ]


async def test_players_service_returns_none_for_missing_mode_stats() -> None:
    service = _service()

    ranked = await service.fetch_player_mode_stats_with_ranks(
        player_id=3,
        mode=1,
        country="ca",
    )

    assert ranked is None


async def test_players_service_lists_all_mode_stats_with_ranks() -> None:
    player_leaderboards = _FakePlayerLeaderboardsService(
        ranks=players.ModeRanks(global_rank=7, country_rank=None),
    )
    service = _service(player_leaderboards=player_leaderboards)

    listing = await service.fetch_player_stats_with_ranks(
        player_id=3,
        country="ca",
        page=1,
        page_size=50,
    )

    assert listing.total_stats == 2
    assert [stat.mode for stat in listing.stats] == [0, 4]
    assert all(stat.rank == 7 for stat in listing.stats)
    assert all(stat.country_rank is None for stat in listing.stats)
    assert player_leaderboards.calls == [
        {"player_id": 3, "mode": 0, "country": "ca"},
        {"player_id": 3, "mode": 4, "country": "ca"},
    ]
