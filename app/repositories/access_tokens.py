from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import Literal
from typing import TypedDict
from uuid import UUID

import app.state.services
from app.api.v2.common import json

ACCESS_TOKEN_TTL = timedelta(hours=1)


class AccessToken(TypedDict):
    refresh_token: UUID | None
    client_id: int
    grant_type: str
    scope: str
    player_id: int | None
    created_at: datetime
    expires_at: datetime


def create_access_token_key(code: UUID | Literal["*"]) -> str:
    return f"bancho:access_tokens:{code}"


async def create(
    access_token_id: UUID,
    client_id: int,
    grant_type: str,
    scope: str,
    refresh_token: UUID | None = None,
    player_id: int | None = None,
) -> AccessToken:
    now = datetime.now()
    expires_at = now + ACCESS_TOKEN_TTL
    access_token: AccessToken = {
        "refresh_token": refresh_token,
        "client_id": client_id,
        "grant_type": grant_type,
        "scope": scope,
        "player_id": player_id,
        "created_at": now,
        "expires_at": expires_at,
    }
    await app.state.services.redis.set(
        create_access_token_key(access_token_id),
        json.dumps(access_token),
        exat=expires_at,
    )
    return access_token


async def fetch_one(access_token_id: UUID) -> AccessToken | None:
    raw_access_token = await app.state.services.redis.get(
        create_access_token_key(access_token_id),
    )
    if raw_access_token is None:
        return None
    return json.loads(raw_access_token)


async def fetch_all(
    client_id: int | None = None,
    scope: str | None = None,
    grant_type: str | None = None,
    player_id: int | None = None,
    page: int = 1,
    page_size: int = 10,
) -> list[AccessToken]:
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


async def delete(access_token_id: UUID) -> AccessToken | None:
    access_token_key = create_access_token_key(access_token_id)

    raw_access_token = await app.state.services.redis.get(access_token_key)
    if raw_access_token is None:
        return None

    await app.state.services.redis.delete(access_token_key)

    return json.loads(raw_access_token)
