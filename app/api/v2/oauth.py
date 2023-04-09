""" bancho.py's v2 apis for interacting with clans """
from __future__ import annotations

import uuid
from typing import Any
from typing import Optional
from typing import Union

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Response
from fastapi import status
from fastapi.param_functions import Form
from fastapi.param_functions import Query

from app.api.v2 import get_current_client
from app.api.v2.common import responses
from app.api.v2.common.oauth import get_credentials_from_basic_auth
from app.api.v2.models.oauth import Token
from app.repositories import access_tokens as access_tokens_repo
from app.repositories import authorization_codes as authorization_codes_repo
from app.repositories import ouath_clients as clients_repo
from app.repositories import refresh_tokens as refresh_tokens_repo

router = APIRouter()


@router.get("/oauth/authorize", status_code=status.HTTP_302_FOUND)
async def authorize(
    client_id: int = Query(),
    redirect_uri: str = Query(),
    response_type: str = Query(regex="code"),
    player_id: int = Query(),
    scope: str = Query(default="", regex=r"\b\w+\b(?:,\s*\b\w+\b)*"),
    state: str = Query(default=None),
) -> str:
    """Authorize a client to access the API on behalf of a user."""
    # NOTE: We should have to implement the frontend part to request the user to authorize the client
    # and then redirect to the redirect_uri with the code.
    # For now, we just return the code and the state if it's provided.
    client = await clients_repo.fetch_one(client_id)
    if client is None:
        return responses.failure("invalid_client")

    if client["redirect_uri"] != redirect_uri:
        return responses.failure("invalid_client")

    if response_type != "code":
        return responses.failure("unsupported_response_type")

    code = uuid.uuid4()
    await authorization_codes_repo.create(code, client_id, scope, player_id)

    if state is None:
        redirect_uri = f"{redirect_uri}?code={code}"
    else:
        redirect_uri = f"{redirect_uri}?code={code}&state={state}"

    # return RedirectResponse(redirect_uri, status_code=status.HTTP_302_FOUND)
    return redirect_uri


@router.post("/oauth/token", status_code=status.HTTP_200_OK)
async def token(
    response: Response,
    grant_type: str = Form(),
    client_id: int = Form(default=None),
    client_secret: str = Form(default=None),
    auth_credentials: Optional[dict[str, Any]] = Depends(
        get_credentials_from_basic_auth,
    ),
    code: Optional[str] = Form(default=None),
    scope: str = Form(default="", regex=r"\b\w+\b(?:,\s*\b\w+\b)*"),
) -> Token:
    """Get an access token for the API."""
    # https://www.rfc-editor.org/rfc/rfc6749#section-5.1
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"

    if (client_id is None or client_secret is None) and auth_credentials is None:
        return responses.failure("invalid_request")

    if client_id is None and client_secret is None:
        if auth_credentials is None:
            return responses.failure("invalid_request")
        else:
            client_id = auth_credentials["client_id"]
            client_secret = auth_credentials["client_secret"]

    client = await clients_repo.fetch_one(client_id)
    if client is None:
        return responses.failure("invalid_client")

    if client["secret"] != client_secret:
        return responses.failure("invalid_client")

    if grant_type == "authorization_code":
        if code is None:
            return responses.failure("invalid_request")

        authorization_code = await authorization_codes_repo.fetch_one(code)
        if not authorization_code:
            return responses.failure("invalid_grant")

        if authorization_code["client_id"] != client_id:
            return responses.failure("invalid_client")

        if authorization_code["scopes"] != scope:
            return responses.failure("invalid_scope")
        await authorization_codes_repo.delete(code)

        refresh_token = uuid.uuid4()
        raw_access_token = uuid.uuid4()

        access_token = await access_tokens_repo.create(
            raw_access_token,
            client_id,
            grant_type,
            scope,
            refresh_token,
            authorization_code["player_id"],
        )
        await refresh_tokens_repo.create(
            refresh_token,
            raw_access_token,
            client_id,
            scope,
        )

        return Token(
            access_token=str(raw_access_token),
            refresh_token=str(refresh_token),
            token_type="Bearer",
            expires_in=3600,
            expires_at=access_token["expires_at"],
            scope=scope,
        )
    elif grant_type == "client_credentials":
        client = await clients_repo.fetch_one(client_id)
        if client is None:
            return responses.failure("invalid_client")

        if client["secret"] != client_secret:
            return responses.failure("invalid_client")

        raw_access_token = uuid.uuid4()
        access_token = await access_tokens_repo.create(
            raw_access_token,
            client_id,
            grant_type,
            scope,
            expires_in=86400,
        )

        return Token(
            access_token=str(raw_access_token),
            refresh_token=None,
            token_type="Bearer",
            expires_in=86400,
            expires_at=access_token["expires_at"],
            scope=scope,
        )
    else:
        return responses.failure("unsupported_grant_type")


@router.post("/oauth/refresh", status_code=status.HTTP_200_OK)
async def refresh(
    response: Response,
    client: dict[str, Any] = Depends(get_current_client),
    grant_type: str = Form(),
    refresh_token: str = Form(),
) -> Token:
    """Refresh an access token."""
    # https://www.rfc-editor.org/rfc/rfc6749#section-5.1
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"

    if grant_type != "refresh_token":
        return responses.failure("unsupported_grant_type")

    if client["grant_type"] != "authorization_code":
        return responses.failure("invalid_grant")

    if client["refresh_token"] != refresh_token:
        return responses.failure("invalid_grant")

    raw_access_token = uuid.uuid4()
    access_token = await access_tokens_repo.create(
        raw_access_token,
        client["client_id"],
        client["grant_type"],
        client["scope"],
        refresh_token,
        client["player_id"],
    )

    return Token(
        access_token=str(raw_access_token),
        refresh_token=refresh_token,
        token_type="Bearer",
        expires_in=3600,
        expires_at=access_token["expires_at"],
        scope=access_token["scope"],
    )
