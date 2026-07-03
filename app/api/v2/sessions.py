"""bancho.py's v2 apis for web session management"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import status
from fastapi.security import HTTPAuthorizationCredentials as HTTPCredentials
from fastapi.security import HTTPBearer

from app.api import dependencies as api_dependencies
from app.api.v2.common import responses
from app.api.v2.common.responses import Failure
from app.api.v2.common.responses import Success
from app.api.v2.models.players import Player
from app.api.v2.models.sessions import LoginRequest
from app.api.v2.models.sessions import Session
from app.services.web_sessions import WebSessionsService

router = APIRouter()

http_bearer_scheme = HTTPBearer(auto_error=False)


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
async def create_session(
    args: LoginRequest,
    web_sessions_service: Annotated[
        WebSessionsService,
        Depends(api_dependencies.get_web_sessions_service),
    ],
) -> Success[Session] | Failure:
    session = await web_sessions_service.login(
        username=args.username,
        password=args.password,
    )
    if session is None:
        return responses.failure(
            message="Incorrect username or password.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    response = Session(token=session.token, player_id=session.user_id)
    return responses.success(response, status_code=status.HTTP_201_CREATED)


@router.get("/sessions/current")
async def get_current_session(
    credentials: Annotated[
        HTTPCredentials | None,
        Depends(http_bearer_scheme),
    ],
    web_sessions_service: Annotated[
        WebSessionsService,
        Depends(api_dependencies.get_web_sessions_service),
    ],
) -> Success[Player] | Failure:
    if credentials is None:
        return responses.failure(
            message="Authentication required.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    user = await web_sessions_service.fetch_session_user(credentials.credentials)
    if user is None:
        return responses.failure(
            message="Invalid or expired session.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    response = Player.model_validate(user)
    return responses.success(response)


@router.delete("/sessions/current")
async def delete_current_session(
    credentials: Annotated[
        HTTPCredentials | None,
        Depends(http_bearer_scheme),
    ],
    web_sessions_service: Annotated[
        WebSessionsService,
        Depends(api_dependencies.get_web_sessions_service),
    ],
) -> Success[None] | Failure:
    if credentials is None:
        return responses.failure(
            message="Authentication required.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    await web_sessions_service.logout(credentials.credentials)
    return responses.success(None)
