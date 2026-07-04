"""shared parameter types for bancho.py's v2 apis"""

from __future__ import annotations

from typing import Annotated

from fastapi import Cookie
from fastapi import Depends
from pydantic import AfterValidator

from app.api import dependencies as api_dependencies
from app.constants.gamemodes import GameMode
from app.repositories.users import User
from app.services.web_sessions import WebSessionsService


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


async def get_optional_session_user(
    web_sessions_service: Annotated[
        WebSessionsService,
        Depends(api_dependencies.get_web_sessions_service),
    ],
    session_token: SessionCookie = None,
) -> User | None:
    """Resolve the (optional) signed-in user from the web session cookie,
    for endpoints whose responses vary by viewer (e.g. visibility rules)."""
    if session_token is None:
        return None
    return await web_sessions_service.fetch_session_user(session_token)


# the signed-in user, or None for anonymous/expired sessions; endpoints
# with viewer-dependent visibility rules take this as a parameter.
OptionalSessionUser = Annotated[User | None, Depends(get_optional_session_user)]
