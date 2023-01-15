from __future__ import annotations

from typing import Any
from typing import Literal
from typing import Optional
from typing import Union
from uuid import UUID

import app.state.services
from app.api.v2.common import json


def create_authorization_code_key(code: Union[UUID, str]) -> str:
    return f"bancho:authorization_codes:{code}"


async def create(
    code: Union[UUID, str],
    client_id: int,
    scope: str,
    player_id: int,
) -> None:
    await app.state.services.redis.setex(
        create_authorization_code_key(code),
        180,
        client_id,
        json.dumps({"client_id": client_id, "scope": scope, "player_id": player_id}),
    )


async def fetch_one(code: Union[UUID, str]) -> Optional[dict[str, Any]]:
    data = await app.state.services.redis.get(create_authorization_code_key(code))
    if data is None:
        return None

    return json.loads(data)


async def fetch_all(
    client_id: Optional[int] = None,
    scope: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
) -> list[dict[str, Any]]:
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


async def delete(code: Union[UUID, str]) -> Optional[dict[str, Any]]:
    authorization_code_key = create_authorization_code_key(code)

    data = await app.state.services.redis.get(authorization_code_key)
    if data is None:
        return None

    await app.state.services.redis.delete(authorization_code_key)

    return json.loads(data)
