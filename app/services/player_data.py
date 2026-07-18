from __future__ import annotations

import time
from collections.abc import Callable
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Any

from app.constants.gamemodes import GameMode
from app.objects.player import ModeData
from app.objects.player import Player
from app.objects.score import Grade
from app.repositories.leaderboard_ranks import LeaderboardRanksRepository
from app.repositories.stats import StatsRepository
from app.repositories.users import UsersRepository


@dataclass(frozen=True)
class PlayerDataService:
    """Hydrate and persist a player's activity, stats, and leaderboard rank."""

    users: UsersRepository
    stats: StatsRepository
    leaderboard_ranks: LeaderboardRanksRepository
    schedule_background: Callable[[Coroutine[Any, Any, None]], None]
    current_time: Callable[[], float] = time.time

    async def hydrate_stats(self, player: Player) -> None:
        for row in await self.stats.fetch_many(player_id=player.id):
            mode = GameMode(row.mode)
            rank = 0
            if not player.restricted:
                rank = (
                    await self.leaderboard_ranks.fetch_global_rank(
                        player.id,
                        row.mode,
                    )
                    or 0
                )

            player.stats[mode] = ModeData(
                tscore=row.tscore,
                rscore=row.rscore,
                pp=row.pp,
                acc=row.acc,
                plays=row.plays,
                playtime=row.playtime,
                max_combo=row.max_combo,
                total_hits=row.total_hits,
                rank=rank,
                grades={
                    Grade.XH: row.xh_count,
                    Grade.X: row.x_count,
                    Grade.SH: row.sh_count,
                    Grade.S: row.s_count,
                    Grade.A: row.a_count,
                },
            )

    async def update_rank(self, player: Player, mode: GameMode) -> int:
        if player.restricted:
            return 0

        country = player.geoloc["country"]["acronym"]
        stats = player.stats[mode]
        await self.leaderboard_ranks.add_to_global_leaderboard(
            player.id,
            mode.value,
            stats.pp,
        )
        await self.leaderboard_ranks.add_to_country_leaderboard(
            player.id,
            mode.value,
            country,
            stats.pp,
        )
        rank = await self.leaderboard_ranks.fetch_global_rank(player.id, mode.value)
        return rank or 0

    async def update_latest_activity(self, player: Player) -> None:
        await self.users.partial_update(
            id=player.id,
            latest_activity=int(self.current_time()),
        )

    def schedule_latest_activity_update(self, player: Player) -> None:
        self.schedule_background(self.update_latest_activity(player))
