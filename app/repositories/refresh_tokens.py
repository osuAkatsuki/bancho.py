from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import Literal
from typing import Optional
from typing import Union
from uuid import UUID

import app.state.services
from app.api.v2.common import json


def create_refresh_token_key(code: UUID | str) -> str:
    return f"bancho:refresh_tokens:{code}"


async def create(
    refresh_token: UUID | str,
    access_token: UUID | str,
    client_id: int,
    scope: str,
) -> dict[str, Any]:
    refresh_token_key = create_refresh_token_key(refresh_token)
    now = datetime.now()
    refresh_token_expires_at = now + timedelta(days=30)

    data = {
        "client_id": client_id,
        "scope": scope,
        "access_token": access_token,
        "created_at": now.isoformat(),
        "expires_at": refresh_token_expires_at.isoformat(),
    }
    await app.state.services.redis.hmset(refresh_token_key, data)
    await app.state.services.redis.expireat(refresh_token_key, refresh_token_expires_at)

    return data


async def fetch_one(refresh_token: UUID | str) -> dict[str, Any] | None:
    data = await app.state.services.redis.hgetall(
        create_refresh_token_key(refresh_token),
    )
    if data is None:
        return None

    return data


async def fetch_all(
    client_id: int | None = None,
    scope: str | None = None,
    page: int = 1,
    page_size: int = 10,
) -> list[dict[str, Any]]:
    refresh_token_key = create_refresh_token_key("*")

    if page > 1:
        cursor, keys = await app.state.services.redis.scan(
            cursor=0,
            match=refresh_token_key,
            count=(page - 1) * page_size,
        )
    else:
        cursor = None

    refresh_tokens = []
    while cursor != 0:
        cursor, keys = await app.state.services.redis.scan(
            cursor=cursor or 0,
            match=refresh_token_key,
            count=page_size,
        )

        raw_refresh_token = await app.state.services.redis.mget(keys)
        for raw_refresh_token in raw_refresh_token:
            refresh_token = json.loads(raw_refresh_token)

            if client_id is not None and refresh_token["client_id"] != client_id:
                continue

            if scope is not None and refresh_token["scope"] != scope:
                continue

            refresh_tokens.append(refresh_token)

    return refresh_tokens


async def delete(refresh_token: UUID | str) -> dict[str, Any] | None:
    refresh_token_key = create_refresh_token_key(refresh_token)

    data = await app.state.services.redis.hgetall(refresh_token_key)
    if data is None:
        return None

    await app.state.services.redis.delete(refresh_token_key)

    return data
