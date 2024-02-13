from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from typing import Literal
from typing import TypedDict
from uuid import UUID

import app.state.services
from app.api.v2.common import json

AUTHORIZATION_CODE_TTL = timedelta(minutes=3)


class AuthorizationCode(TypedDict):
    client_id: int
    scope: str
    player_id: int
    created_at: datetime
    expires_at: datetime


def create_authorization_code_key(code: UUID | Literal["*"]) -> str:
    return f"bancho:authorization_codes:{code}"


async def create(
    code: UUID,
    client_id: int,
    scope: str,
    player_id: int,
) -> AuthorizationCode:
    now = datetime.now()
    expires_at = now + AUTHORIZATION_CODE_TTL
    authorization_code: AuthorizationCode = {
        "client_id": client_id,
        "scope": scope,
        "player_id": player_id,
        "created_at": now,
        "expires_at": expires_at,
    }
    await app.state.services.redis.set(
        create_authorization_code_key(code),
        json.dumps(authorization_code),
        exat=expires_at,
    )
    return authorization_code


async def fetch_one(code: UUID) -> AuthorizationCode | None:
    raw_authorization_code = await app.state.services.redis.get(
        create_authorization_code_key(code),
    )
    if raw_authorization_code is None:
        return None

    return json.loads(raw_authorization_code)


async def fetch_all(
    client_id: int | None = None,
    scope: str | None = None,
    page: int = 1,
    page_size: int = 10,
) -> list[AuthorizationCode]:
    authorization_code_key = create_authorization_code_key("*")

    if page > 1:
        cursor, keys = await app.state.services.redis.scan(
            cursor=0,
            match=authorization_code_key,
            count=(page - 1) * page_size,
        )
    else:
        cursor = None

    authorization_codes = []
    while cursor != 0:
        cursor, keys = await app.state.services.redis.scan(
            cursor=cursor or 0,
            match=authorization_code_key,
            count=page_size,
        )

        raw_authorization_code = await app.state.services.redis.mget(keys)
        for raw_authorization_code in raw_authorization_code:
            authorization_code = json.loads(raw_authorization_code)

            if client_id is not None and authorization_code["client_id"] != client_id:
                continue

            if scope is not None and authorization_code["scope"] != scope:
                continue

            authorization_codes.append(authorization_code)

    return authorization_codes


async def delete(code: UUID) -> AuthorizationCode | None:
    authorization_code_key = create_authorization_code_key(code)

    raw_authorization_code = await app.state.services.redis.get(authorization_code_key)
    if raw_authorization_code is None:
        return None

    await app.state.services.redis.delete(authorization_code_key)

    return json.loads(raw_authorization_code)
