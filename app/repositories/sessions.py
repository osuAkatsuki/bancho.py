from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import Literal
from typing import Mapping
from typing import Union
from uuid import UUID

import app.settings
import app.state.services
from app.api.v2.common import json


def create_session_key(session_id: Union[UUID, Literal["*"]]):
    return f"bancho:sessions:{session_id}"


async def create(session_id: UUID, player_id: int) -> Mapping[str, Any]:
    now = datetime.now()
    expires_at = now + timedelta(seconds=app.settings.SESSION_EXPIRY)
    session = {
        "session_id": session_id,
        "player_id": player_id,
        "expires_at": expires_at,
        "created_at": now,
        "updated_at": now,
    }
    await app.state.services.redis.setex(
        create_session_key(session_id),
        app.settings.SESSION_EXPIRY,
        json.dumps(session),
    )
    return session


async def fetch_one(session_id: UUID) -> Union[Mapping[str, Any], None]:
    session = await app.state.services.redis.get(create_session_key(session_id))
    if session is None:
        return None
    return json.loads(session)


async def delete(session_id: UUID) -> Union[Mapping[str, Any], None]:
    session_key = create_session_key(session_id)

    session = await app.state.services.redis.get(session_key)
    if session is None:
        return None

    await app.state.services.redis.delete(session_key)

    return json.loads(session)
