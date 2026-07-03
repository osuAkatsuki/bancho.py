from __future__ import annotations

from dataclasses import dataclass

from app.constants.gamemodes import GameMode
from app.repositories.leaderboard_ranks import LeaderboardRanksRepository
from app.repositories.stats import LeaderboardStatsRow
from app.repositories.stats import StatsRepository


@dataclass(frozen=True)
class ModeRanks:
    # A rank of None means the player is unranked for the mode.
    global_rank: int | None
    country_rank: int | None


@dataclass(frozen=True)
class PlayerLeaderboardsService:
    stats: StatsRepository
    leaderboard_ranks: LeaderboardRanksRepository

    async def fetch_global_leaderboard(
        self,
        *,
        sort: str,
        mode: GameMode,
        limit: int,
        offset: int,
        country: str | None,
    ) -> list[LeaderboardStatsRow]:
        return await self.stats.fetch_leaderboard_stats_rows(
            sort=sort,
            mode=int(mode),
            limit=limit,
            offset=offset,
            country=country,
        )

    async def fetch_player_mode_ranks(
        self,
        *,
        player_id: int,
        mode: int,
        country: str,
    ) -> ModeRanks:
        return ModeRanks(
            global_rank=await self.leaderboard_ranks.fetch_global_rank(
                player_id,
                mode,
            ),
            country_rank=await self.leaderboard_ranks.fetch_country_rank(
                player_id,
                mode,
                country,
            ),
        )
