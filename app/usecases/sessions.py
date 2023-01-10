from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime
from typing import Any
from typing import Mapping
from typing import Union
from uuid import UUID
from uuid import uuid4

import bcrypt

from app.api.v2.models.sessions import SessionUpdate
from app.repositories import players as players_repo
from app.repositories import sessions as sessions_repo

# NOTE: Should be palced in separate module and re-used in /login endpoint
async def check_password(password: str, hashed: str) -> bool:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        bcrypt.checkpw,
        password.encode("utf-8"),
        hashed.encode("utf-8"),
    )


async def authorize(username: str, password: str) -> Union[Mapping[str, Any], None]:
    player = await players_repo.fetch_one(name=username, fetch_all_fields=True)
    if player is None:
        # We should have errors enum
        return None

    player_id = player["id"]
    hashed_password = player["pw_bcrypt"]

    if not await check_password(
        hashlib.md5(password.encode("UTF-8")).hexdigest(),
        hashed_password,
    ):
        return None

    session_id = uuid4()
    session = await sessions_repo.create(session_id=session_id, player_id=player_id)

    return session


async def deauthorize(session_id: UUID) -> Union[Mapping[str, Any], None]:
    session = await sessions_repo.delete(session_id)
    if session is None:
        return None

    return session


async def partial_update(
    session_id: UUID,
    **kwargs: Any | None,
) -> Union[Mapping[str, Any], None]:

    updates = {
        field: kwargs[field] for field in SessionUpdate.__fields__ if field in kwargs
    }

    session = await sessions_repo.partial_update(session_id, **updates)
    if session is None:
        return None

    return session
