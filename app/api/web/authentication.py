from __future__ import annotations

from collections.abc import Awaitable
from collections.abc import Callable
from functools import cache
from typing import Any
from urllib.parse import unquote

from fastapi import status
from fastapi.exceptions import HTTPException

import app.state
from app.objects.player import Player


@cache
def authenticate_player_session(
    param_function: Callable[..., Any],
    username_alias: str = "u",
    pw_md5_alias: str = "p",
    err: Any | None = None,
) -> Callable[[str, str], Awaitable[Player]]:
    async def wrapper(
        username: str = param_function(..., alias=username_alias),
        pw_md5: str = param_function(..., alias=pw_md5_alias),
    ) -> Player:
        player = await app.state.sessions.players.from_login(
            name=unquote(username),
            pw_md5=pw_md5,
        )
        if player:
            return player

        # player login incorrect
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=err,
        )

    return wrapper
