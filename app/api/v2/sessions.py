"""bancho.py's v2 apis for web session management"""

from __future__ import annotations

from typing import Annotated
from typing import cast

from fastapi import APIRouter
from fastapi import Cookie
from fastapi import Depends
from fastapi import Response
from fastapi import status

from app import settings
from app.api import dependencies as api_dependencies
from app.api.v2.common import responses
from app.api.v2.common.responses import Failure
from app.api.v2.common.responses import Success
from app.api.v2.models.players import Player
from app.api.v2.models.sessions import LoginRequest
from app.services.web_sessions import WEB_SESSION_EXPIRY_SECONDS
from app.services.web_sessions import WebSessionsService

router = APIRouter()

WEB_SESSION_COOKIE_NAME = "bancho_session"

# the session token is transported exclusively via an http-only cookie,
# so that scripts running in the browser can never read it.
SessionCookie = Annotated[str | None, Cookie(alias=WEB_SESSION_COOKIE_NAME)]


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=WEB_SESSION_COOKIE_NAME,
        value=token,
        max_age=WEB_SESSION_EXPIRY_SECONDS,
        path="/",
        httponly=True,
        secure=settings.WEB_SESSION_COOKIE_SECURE,
        samesite="lax",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=WEB_SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=settings.WEB_SESSION_COOKIE_SECURE,
        samesite="lax",
    )


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
async def create_session(
    args: LoginRequest,
    web_sessions_service: Annotated[
        WebSessionsService,
        Depends(api_dependencies.get_web_sessions_service),
    ],
) -> Success[Player] | Failure:
    session = await web_sessions_service.login(
        username=args.username,
        password=args.password,
    )
    if session is None:
        return responses.failure(
            message="Incorrect username or password.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    success_response = responses.success(
        Player.model_validate(session.user),
        status_code=status.HTTP_201_CREATED,
    )
    # the responses helpers type their return values as the response
    # models for openapi purposes, but return http responses at runtime.
    _set_session_cookie(cast(Response, success_response), session.token)
    return success_response


@router.get("/sessions/current")
async def get_current_session(
    session_token: SessionCookie = None,
    *,
    web_sessions_service: Annotated[
        WebSessionsService,
        Depends(api_dependencies.get_web_sessions_service),
    ],
) -> Success[Player] | Failure:
    if session_token is None:
        return responses.failure(
            message="Authentication required.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    user = await web_sessions_service.fetch_session_user(session_token)
    if user is None:
        return responses.failure(
            message="Invalid or expired session.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    response = Player.model_validate(user)
    return responses.success(response)


@router.delete("/sessions/current")
async def delete_current_session(
    session_token: SessionCookie = None,
    *,
    web_sessions_service: Annotated[
        WebSessionsService,
        Depends(api_dependencies.get_web_sessions_service),
    ],
) -> Success[None] | Failure:
    if session_token is None:
        return responses.failure(
            message="Authentication required.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    await web_sessions_service.logout(session_token)

    success_response = responses.success(None)
    _clear_session_cookie(cast(Response, success_response))
    return success_response
