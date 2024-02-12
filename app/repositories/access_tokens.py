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


def create_access_token_key(code: UUID | str) -> str:
    return f"bancho:access_tokens:{code}"


async def create(
    access_token: UUID | str,
    client_id: int,
    grant_type: str,
    scope: str,
    refresh_token: UUID | str | None = "",
    player_id: int | None = "",
    expires_in: int | None = "",
) -> dict[str, Any]:
    access_token_key = create_access_token_key(access_token)
    now = datetime.now()
    access_token_expires_at = now + timedelta(seconds=expires_in or 3600)

    data = {
        "refresh_token": refresh_token,
        "client_id": client_id,
        "grant_type": grant_type,
        "scope": scope,
        "player_id": player_id,
        "created_at": now.isoformat(),
        "expires_at": access_token_expires_at.isoformat(),
    }
    await app.state.services.redis.hmset(access_token_key, data)
    await app.state.services.redis.expireat(access_token_key, access_token_expires_at)

    return data


async def fetch_one(access_token: UUID | str) -> dict[str, Any] | None:
    data = await app.state.services.redis.hgetall(create_access_token_key(access_token))

    if data is None:
        return None

    return data


async def fetch_all(
    client_id: int | None = None,
    scope: str | None = None,
    grant_type: str | None = None,
    player_id: int | None = None,
    page: int = 1,
    page_size: int = 10,
) -> list[dict[str, Any]]:
    access_token_key = create_access_token_key("*")

    if page > 1:
        cursor, keys = await app.state.services.redis.scan(
            cursor=0,
            match=access_token_key,
            count=(page - 1) * page_size,
        )
    else:
        cursor = None

    access_tokens = []
    while cursor != 0:
        cursor, keys = await app.state.services.redis.scan(
            cursor=cursor or 0,
            match=access_token_key,
            count=page_size,
        )

        raw_access_token = await app.state.services.redis.mget(keys)
        for raw_access_token in raw_access_token:
            access_token = json.loads(raw_access_token)

            if client_id is not None and access_token["client_id"] != client_id:
                continue

            if scope is not None and access_token["scopes"] != scope:
                continue

            if grant_type is not None and access_token["grant_type"] != grant_type:
                continue

            if player_id is not None and access_token["player_id"] != player_id:
                continue

            access_tokens.append(access_token)

    return access_tokens


async def delete(access_token: UUID | str) -> dict[str, Any] | None:
    access_token_key = create_access_token_key(access_token)

    data = await app.state.services.redis.hgetall(access_token_key)
    if data is None:
        return None

    await app.state.services.redis.delete(access_token_key)

    return data
