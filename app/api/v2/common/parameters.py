"""shared parameter types for bancho.py's v2 apis"""

from __future__ import annotations

from typing import Annotated

from fastapi import Cookie
from pydantic import AfterValidator

from app.constants.gamemodes import GameMode


def _validate_gamemode(mode: int) -> int:
    if mode not in GameMode.valid_gamemodes():
        raise ValueError(
            "invalid gamemode; valid values are "
            f"{', '.join(str(int(m)) for m in GameMode.valid_gamemodes())}",
        )
    return mode


# a playable gamemode id (0-3 vanilla, 4-6 relax, 8 autopilot);
# 7 and 9-11 are rejected with a request validation error.
GameModeParam = Annotated[int, AfterValidator(_validate_gamemode)]

WEB_SESSION_COOKIE_NAME = "bancho_session"

# the session token is transported exclusively via an http-only cookie,
# so that scripts running in the browser can never read it.
SessionCookie = Annotated[str | None, Cookie(alias=WEB_SESSION_COOKIE_NAME)]
