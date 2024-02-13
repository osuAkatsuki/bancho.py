""" bancho.py's v2 apis for interacting with clans """

from __future__ import annotations

import urllib.parse
import uuid
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import Literal

import jwt
from fastapi import APIRouter
from fastapi import Depends
from fastapi import Response
from fastapi import status
from fastapi.param_functions import Form
from fastapi.param_functions import Query

from app import settings
from app.api.v2 import AuthorizationContext
from app.api.v2 import authenticate_api_request
from app.api.v2.common.oauth import BasicAuthCredentials
from app.api.v2.common.oauth import get_credentials_from_basic_auth
from app.api.v2.models.oauth import AuthorizationCodeGrantData
from app.api.v2.models.oauth import ClientCredentialsGrantData
from app.api.v2.models.oauth import GrantType
from app.api.v2.models.oauth import Token
from app.api.v2.models.oauth import TokenType
from app.repositories import authorization_codes as authorization_codes_repo
from app.repositories import ouath_clients as clients_repo
from app.repositories import refresh_tokens as refresh_tokens_repo

router = APIRouter()

ACCESS_TOKEN_TTL = timedelta(minutes=5)


def oauth_failure_response(reason: str) -> dict[str, Any]:
    return {"error": reason}


def generate_authorization_code() -> str:
    return str(uuid.uuid4())


@router.get("/oauth/authorize", status_code=status.HTTP_302_FOUND)
async def authorize(
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    # TODO: support for "token" response type in implcit flow?
    #       https://www.rfc-editor.org/rfc/rfc6749#section-3.1.1
    response_type: Literal["code"] = Query(...),
    player_id: int = Query(...),
    scope: str | None = Query(default=None, regex=r"\b\w+\b(?:,\s*\b\w+\b)*"),
    state: str | None = Query(default=None),  # csrf protection
):
    """\
    Authorize a client to access the API on behalf of a user.

    Used by the authorizaton_grant and implicit grant flows.
    """
    # NOTE: We should have to implement the frontend part to request the user to authorize the client
    # and then redirect to the redirect_uri with the code.
    # For now, we just return the code and the state if it's provided.
    client = await clients_repo.fetch_one(client_id)
    if client is None:
        return oauth_failure_response("invalid_client")

    if client["redirect_uri"] != redirect_uri:
        return oauth_failure_response("invalid_client")

    if response_type != "code":
        return oauth_failure_response("unsupported_response_type")

    code = generate_authorization_code()
    await authorization_codes_repo.create(code, client_id, scope, player_id)

    params: dict[str, Any] = {
        "code": code,
    }
    if state is not None:
        params["state"] = state

    redirect_uri = redirect_uri + "?" + urllib.parse.urlencode(params)

    return redirect_uri


def generate_access_token(
    access_token_id: uuid.UUID,
    issued_at: datetime,
    expires_at: datetime,
    client_id: str,
    grant_type: GrantType,
    scope: str | None,
    issuer: str = "bancho",
    audiences: list[str] = ["bancho"],
    additional_claims: dict[str, Any] | None = None,
) -> str:
    if additional_claims is None:
        additional_claims = {}
    new_claims = {
        # registered claims
        "exp": expires_at,
        "nbf": issued_at,
        "iss": issuer,
        "aud": audiences,
        "iat": issued_at,
        # unregistered claims
        "access_token_id": access_token_id,
        "client_id": client_id,
        "grant_type": grant_type.value,
        "scope": scope,
        **additional_claims,
    }
    raw_access_token = jwt.encode(
        new_claims,
        settings.JWT_PRIVATE_KEY,
        algorithm="HS256",
    )
    return raw_access_token


def generate_refresh_token(
    refresh_token_id: uuid.UUID,
    issued_at: datetime,
    expires_at: datetime,
    client_id: str,
    scope: str | None,
    issuer: str = "bancho",
    audiences: list[str] = ["bancho"],
    additional_claims: dict[str, Any] | None = None,
) -> str:
    if additional_claims is None:
        additional_claims = {}
    new_claims = {
        # registered claims
        "exp": expires_at,
        "nbf": issued_at,
        "iss": issuer,
        "aud": audiences,
        "iat": issued_at,
        # unregistered claims
        "refresh_token_id": refresh_token_id,
        "client_id": client_id,
        "scope": scope,
        **additional_claims,
    }
    raw_refresh_token = jwt.encode(
        new_claims,
        settings.JWT_PRIVATE_KEY,
        algorithm="HS256",
    )
    return raw_refresh_token


@router.post("/oauth/token", status_code=status.HTTP_200_OK)
async def token(
    response: Response,
    grant_type: GrantType = Form(),
    scope: str | None = Form(default=None, regex=r"\b\w+\b(?:,\s*\b\w+\b)*"),
    # specific args to authorization code grant
    code: str | None = Form(None),
    redirect_uri: str | None = Form(None),
    client_id: str | None = Form(None),
    # args specific to refresh grant
    refresh_token: str = Form(...),
    # TODO: support basic authentication
    # auth_credentials: BasicAuthCredentials | None = Depends(
    #     get_credentials_from_basic_auth,
    # ),
):
    """Get an access token for the API."""
    # https://www.rfc-editor.org/rfc/rfc6749#section-5.1
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"

    if grant_type is GrantType.CLIENT_CREDENTIALS:
        client_credentials_grant_data = ClientCredentialsGrantData(scope=scope)

    elif grant_type is GrantType.AUTHORIZATION_CODE:
        if code is None or redirect_uri is None or client_id is None:
            return oauth_failure_response("invalid_request")

        authorization_code_grant_form = AuthorizationCodeGrantData(
            code=code,
            redirect_uri=redirect_uri,
            client_id=client_id,
        )

        client = await clients_repo.fetch_one(client_id)
        if client is None:
            return oauth_failure_response("invalid_client")

        if client["secret"] != code:
            return oauth_failure_response("invalid_client")
        ...
    elif grant_type is GrantType.REFRESH_TOKEN:
        ...
    else:
        return oauth_failure_response("unsupported_grant_type")

    if (client_id is None or client_secret is None) and auth_credentials is None:
        return oauth_failure_response("invalid_request")

    if client_id is None and client_secret is None:
        if auth_credentials is None:
            return oauth_failure_response("invalid_request")
        else:
            client_id = auth_credentials["client_id"]
            client_secret = auth_credentials["client_secret"]

    client = await clients_repo.fetch_one(client_id)
    if client is None:
        return oauth_failure_response("invalid_client")

    if client["secret"] != client_secret:
        return oauth_failure_response("invalid_client")

    if grant_type is GrantType.AUTHORIZATION_CODE:
        if authorization_code_grant_form is None:
            return oauth_failure_response("invalid_request")

        if authorization_code_grant_form.code is None:
            return oauth_failure_response("invalid_request")

        authorization_code = await authorization_codes_repo.fetch_one(
            authorization_code_grant_form.code,
        )
        if not authorization_code:
            return oauth_failure_response("invalid_grant")

        if client_id is None or authorization_code["client_id"] != client_id:
            return oauth_failure_response("invalid_client")

        if authorization_code["scope"] != scope:
            return oauth_failure_response("invalid_scope")

        await authorization_codes_repo.delete(code)

        access_token_id = uuid.uuid4()
        now = datetime.now()
        expires_at = now + ACCESS_TOKEN_TTL
        raw_access_token = generate_access_token(
            access_token_id=access_token_id,
            issued_at=now,
            expires_at=expires_at,
            client_id=str(client_id),
            grant_type=grant_type,
            scope=scope,
            additional_claims={"player_id": authorization_code["player_id"]},
        )
        refresh_token_id = uuid.uuid4()

        await refresh_tokens_repo.create(refresh_token_id, client_id, scope)

        return Token(
            access_token=str(raw_access_token),
            refresh_token=str(refresh_token_id),
            token_type=TokenType.BEARER.value,
            expires_in=3600,
            expires_at=expires_at,
            scope=scope,
        )
    elif grant_type is GrantType.CLIENT_CREDENTIALS:
        if client_id is None:
            return oauth_failure_response("invalid_client")

        client = await clients_repo.fetch_one(client_id)
        if client is None:
            return oauth_failure_response("invalid_client")

        if client["secret"] != client_secret:
            return oauth_failure_response("invalid_client")

        access_token_id = uuid.uuid4()
        now = datetime.now()
        expires_at = now + ACCESS_TOKEN_TTL
        raw_access_token = generate_access_token(
            access_token_id=access_token_id,
            issued_at=now,
            expires_at=expires_at,
            client_id=str(client_id),
            grant_type=grant_type,
            scope=scope,
        )
        return Token(
            access_token=raw_access_token,
            refresh_token=None,
            token_type=TokenType.BEARER.value,
            expires_in=int((expires_at - now).total_seconds()),
            expires_at=expires_at,
            scope=scope,
        )
    else:
        return oauth_failure_response("unsupported_grant_type")


@router.post("/oauth/refresh", status_code=status.HTTP_200_OK)
async def refresh(
    response: Response,
    auth_ctx: AuthorizationContext = Depends(authenticate_api_request),
    grant_type: GrantType = Form(),
    raw_refresh_token: str = Form(),
):
    """Refresh an access token."""
    # https://www.rfc-editor.org/rfc/rfc6749#section-5.1
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"

    verified_claims = auth_ctx["verified_claims"]

    if grant_type is not GrantType.REFRESH_TOKEN:
        return oauth_failure_response("unsupported_grant_type")

    if verified_claims["grant_type"] != "authorization_code":
        return oauth_failure_response("invalid_grant")

    if verified_claims["refresh_token"] != raw_refresh_token:
        return oauth_failure_response("invalid_grant")

    access_token_id = uuid.uuid4()
    now = datetime.now()
    expires_at = now + ACCESS_TOKEN_TTL
    raw_access_token = generate_access_token(
        access_token_id=access_token_id,
        issued_at=now,
        expires_at=expires_at,
        client_id=verified_claims["client_id"],
        grant_type=grant_type,
        scope=verified_claims["scope"],
        additional_claims={"player_id": verified_claims["player_id"]},
    )
    # TODO: should we generate a new refresh token?

    return Token(
        access_token=raw_access_token,
        refresh_token=raw_refresh_token,
        token_type=TokenType.BEARER.value,
        expires_in=int((expires_at - now).total_seconds()),
        expires_at=expires_at,
        scope=verified_claims["scope"],
    )
