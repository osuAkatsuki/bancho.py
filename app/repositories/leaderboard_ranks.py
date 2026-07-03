from __future__ import annotations

from typing import cast

from redis import asyncio as aioredis


class LeaderboardRanksRepository:
    """Player leaderboard positions, stored in redis sorted sets."""

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    async def fetch_global_rank(self, player_id: int, mode: int) -> int | None:
        """Fetch a player's 1-indexed global rank for a mode, if ranked."""
        rank = cast(
            "int | None",
            await self._redis.zrevrank(
                f"bancho:leaderboard:{mode}",
                str(player_id),
            ),
        )
        return rank + 1 if rank is not None else None

    async def fetch_country_rank(
        self,
        player_id: int,
        mode: int,
        country: str,
    ) -> int | None:
        """Fetch a player's 1-indexed country rank for a mode, if ranked."""
        rank = cast(
            "int | None",
            await self._redis.zrevrank(
                f"bancho:leaderboard:{mode}:{country}",
                str(player_id),
            ),
        )
        return rank + 1 if rank is not None else None
