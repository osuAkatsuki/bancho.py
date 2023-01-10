""" bancho.py's v2 api's authorization """
from __future__ import annotations

import uuid

from fastapi import APIRouter
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials as HTTPCredentials
from fastapi.security import HTTPBearer

from app.api.v2.common import responses
from app.api.v2.common.responses import Success
from app.api.v2.models.sessions import LoginForm
from app.api.v2.models.sessions import Session
from app.repositories import sessions as sessions_repo
from app.usecases import sessions

router = APIRouter()
oauth2_scheme = HTTPBearer()


@router.post("/sessions")
async def create_session(args: LoginForm) -> Success[Session]:
    data = await sessions.authorize(username=args.username, password=args.password)
    if data is None:
        return responses.failure(message="Failed to create session.")

    response = Session.from_mapping(data)
    return responses.success(response)


@router.get("/sessions/self")
async def get_self_session(
    token: HTTPCredentials = Depends(oauth2_scheme),
) -> Success[Session]:
    data = await sessions_repo.fetch_one(uuid.UUID(token.credentials))
    if data is None:
        return responses.failure(message="Failed to create session.")

    response = Session.from_mapping(data)
    return responses.success(response)


@router.delete("/sessions")
async def delete_session(
    token: HTTPCredentials = Depends(oauth2_scheme),
) -> Success[Session]:
    data = await sessions.deauthorize(uuid.UUID(token.credentials))
    if data is None:
        return responses.failure(message="Failed to create session.")

    response = Session.from_mapping(data)
    return responses.success(response)
