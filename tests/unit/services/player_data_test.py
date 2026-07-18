from __future__ import annotations

from collections.abc import Coroutine
from types import SimpleNamespace
from typing import Any
from typing import cast

from app.constants.gamemodes import GameMode
from app.constants.privileges import Privileges
from app.objects.player import Player
from app.repositories.leaderboard_ranks import LeaderboardRanksRepository
from app.repositories.stats import Stat
from app.repositories.stats import StatsRepository
from app.services.player_data import PlayerDataService


class _FakeUsersRepository:
    def __init__(self) -> None:
        self.updates: list[dict[str, int]] = []

    async def partial_update(self, *, id: int, latest_activity: int) -> None:
        self.updates.append({"id": id, "latest_activity": latest_activity})


class _FakeStatsRepository:
    async def fetch_many(self, *, player_id: int) -> list[Stat]:
        assert player_id == 7
        return [
            Stat(
                id=player_id,
                mode=GameMode.VANILLA_OSU,
                tscore=1,
                rscore=2,
                pp=3,
                plays=4,
                playtime=5,
                acc=6.0,
                max_combo=7,
                total_hits=8,
                replay_views=9,
                xh_count=10,
                x_count=11,
                sh_count=12,
                s_count=13,
                a_count=14,
            ),
        ]


class _FakeLeaderboardRanksRepository:
    def __init__(self, rank: int | None = None) -> None:
        self.rank = rank
        self.fetch_global_rank_calls: list[tuple[int, int]] = []

    async def fetch_global_rank(self, player_id: int, mode: int) -> int | None:
        self.fetch_global_rank_calls.append((player_id, mode))
        return self.rank


async def test_latest_activity_update_is_scheduled_without_blocking_caller() -> None:
    users = _FakeUsersRepository()
    scheduled: list[Coroutine[Any, Any, None]] = []
    service = PlayerDataService(
        users=users,  # type: ignore[arg-type]
        stats=object(),  # type: ignore[arg-type]
        leaderboard_ranks=object(),  # type: ignore[arg-type]
        schedule_background=scheduled.append,
        current_time=lambda: 123.9,
    )

    service.schedule_latest_activity_update(cast(Player, SimpleNamespace(id=7)))

    assert users.updates == []
    assert len(scheduled) == 1

    await scheduled[0]
    assert users.updates == [{"id": 7, "latest_activity": 123}]


async def test_hydrate_stats_does_not_fetch_ranks_for_restricted_player() -> None:
    player = Player(
        id=7,
        name="restricted",
        priv=Privileges.VERIFIED,
        pw_bcrypt=None,
        token=Player.generate_token(),
    )
    ranks = _FakeLeaderboardRanksRepository(rank=12)
    service = PlayerDataService(
        users=cast(Any, _FakeUsersRepository()),
        stats=cast(StatsRepository, _FakeStatsRepository()),
        leaderboard_ranks=cast(LeaderboardRanksRepository, ranks),
        schedule_background=lambda coroutine: None,
    )

    await service.hydrate_stats(player)

    assert player.stats[GameMode.VANILLA_OSU].rank == 0
    assert ranks.fetch_global_rank_calls == []


async def test_hydrate_stats_fetches_only_the_global_rank() -> None:
    player = Player(
        id=7,
        name="unrestricted",
        priv=Privileges.UNRESTRICTED | Privileges.VERIFIED,
        pw_bcrypt=None,
        token=Player.generate_token(),
    )
    ranks = _FakeLeaderboardRanksRepository(rank=12)
    service = PlayerDataService(
        users=cast(Any, _FakeUsersRepository()),
        stats=cast(StatsRepository, _FakeStatsRepository()),
        leaderboard_ranks=cast(LeaderboardRanksRepository, ranks),
        schedule_background=lambda coroutine: None,
    )

    await service.hydrate_stats(player)

    assert player.stats[GameMode.VANILLA_OSU].rank == 12
    assert ranks.fetch_global_rank_calls == [(7, GameMode.VANILLA_OSU.value)]
