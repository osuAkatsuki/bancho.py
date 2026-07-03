from __future__ import annotations

import app.services.player_leaderboards as player_leaderboards
from app.constants.gamemodes import GameMode


class _FakeStatsRepository:
    def __init__(self) -> None:
        self.leaderboard_calls: list[dict[str, object | None]] = []

    async def fetch_leaderboard_stats_rows(
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


class _FakeLeaderboardRanksRepository:
    def __init__(
        self,
        global_ranks: dict[tuple[int, int], int] | None = None,
        country_ranks: dict[tuple[int, int, str], int] | None = None,
    ) -> None:
        self.global_ranks = global_ranks if global_ranks is not None else {}
        self.country_ranks = country_ranks if country_ranks is not None else {}
        self.calls: list[tuple[object, ...]] = []

    async def fetch_global_rank(self, player_id: int, mode: int) -> int | None:
        self.calls.append(("global", player_id, mode))
        return self.global_ranks.get((player_id, mode))

    async def fetch_country_rank(
        self,
        player_id: int,
        mode: int,
        country: str,
    ) -> int | None:
        self.calls.append(("country", player_id, mode, country))
        return self.country_ranks.get((player_id, mode, country))


def _service(
    leaderboard_ranks: _FakeLeaderboardRanksRepository | None = None,
) -> player_leaderboards.PlayerLeaderboardsService:
    if leaderboard_ranks is None:
        leaderboard_ranks = _FakeLeaderboardRanksRepository()

    return player_leaderboards.PlayerLeaderboardsService(
        stats=_FakeStatsRepository(),
        leaderboard_ranks=leaderboard_ranks,
    )


async def test_player_leaderboards_service_fetches_the_global_leaderboard() -> None:
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


async def test_player_leaderboards_service_fetches_player_mode_ranks() -> None:
    leaderboard_ranks = _FakeLeaderboardRanksRepository(
        global_ranks={(3, 0): 5},
        country_ranks={(3, 0, "ca"): 1},
    )
    service = _service(leaderboard_ranks=leaderboard_ranks)

    ranks = await service.fetch_player_mode_ranks(player_id=3, mode=0, country="ca")

    assert ranks == player_leaderboards.ModeRanks(global_rank=5, country_rank=1)
    assert leaderboard_ranks.calls == [
        ("global", 3, 0),
        ("country", 3, 0, "ca"),
    ]


async def test_player_leaderboards_service_reports_unranked_players_as_none() -> None:
    service = _service()

    ranks = await service.fetch_player_mode_ranks(player_id=3, mode=0, country="ca")

    assert ranks == player_leaderboards.ModeRanks(global_rank=None, country_rank=None)
