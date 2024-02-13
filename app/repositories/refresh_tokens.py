from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from typing import Literal
from typing import TypedDict
from uuid import UUID

import app.state.services
from app.api.v2.common import json


class RefreshToken(TypedDict):
    client_id: int
    scope: str
    refresh_token_id: UUID
    access_token_id: UUID
    created_at: datetime
    expires_at: datetime


def create_refresh_token_key(code: UUID | Literal["*"]) -> str:
    return f"bancho:refresh_tokens:{code}"


async def create(
    refresh_token_id: UUID,
    access_token_id: UUID,
    client_id: int,
    scope: str,
) -> RefreshToken:
    now = datetime.now()
    expires_at = now + timedelta(days=30)
    refresh_token: RefreshToken = {
        "client_id": client_id,
        "scope": scope,
        "refresh_token_id": refresh_token_id,
        "access_token_id": access_token_id,
        "created_at": now,
        "expires_at": expires_at,
    }
    await app.state.services.redis.set(
        create_refresh_token_key(refresh_token_id),
        json.dumps(refresh_token),
        exat=expires_at,
    )
    return refresh_token


async def fetch_one(refresh_token_id: UUID) -> RefreshToken | None:
    raw_refresh_token = await app.state.services.redis.get(
        create_refresh_token_key(refresh_token_id),
    )
    if raw_refresh_token is None:
        return None

    return json.loads(raw_refresh_token)


async def fetch_all(
    client_id: int | None = None,
    scope: str | None = None,
    page: int = 1,
    page_size: int = 10,
) -> list[RefreshToken]:
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


async def delete(refresh_token_id: UUID) -> RefreshToken | None:
    refresh_token_key = create_refresh_token_key(refresh_token_id)

    raw_refresh_token = await app.state.services.redis.get(refresh_token_key)
    if raw_refresh_token is None:
        return None

    await app.state.services.redis.delete(refresh_token_key)

    return json.loads(raw_refresh_token)
