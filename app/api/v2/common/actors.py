"""resolution of the acting user ("actor") behind v2 api requests"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.api import dependencies as api_dependencies
from app.api.v2.common.parameters import SessionCookie
from app.repositories.users import User
from app.services.web_sessions import WebSessionsService


async def get_optional_actor(
    web_sessions_service: Annotated[
        WebSessionsService,
        Depends(api_dependencies.get_web_sessions_service),
    ],
    session_token: SessionCookie = None,
) -> User | None:
    """Authenticate the user making the request from the web session
    cookie; None means anonymous (or an expired/revoked session)."""
    if session_token is None:
        return None
    return await web_sessions_service.fetch_session_user(session_token)
