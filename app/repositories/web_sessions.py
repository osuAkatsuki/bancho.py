from __future__ import annotations

from redis import asyncio as aioredis


def _session_key(token: str) -> str:
    return f"bancho:web_sessions:{token}"


class WebSessionsRepository:
    """Web session tokens, stored in redis with a rolling expiry."""

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    async def create(
        self,
        token: str,
        user_id: int,
        expiry_seconds: int,
    ) -> None:
        await self._redis.setex(_session_key(token), expiry_seconds, str(user_id))

    async def fetch_user_id(self, token: str) -> int | None:
        value = await self._redis.get(_session_key(token))
        if value is None:
            return None
        return int(value)

    async def delete(self, token: str) -> None:
        await self._redis.delete(_session_key(token))
