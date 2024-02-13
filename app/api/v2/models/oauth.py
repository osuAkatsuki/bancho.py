from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from . import BaseModel

# input models


class ClientCredentialsGrantData(BaseModel):
    scope: str | None


class AuthorizationCodeGrantData(BaseModel):
    code: str
    redirect_uri: str
    client_id: str


class RefreshGrantData(BaseModel):
    refresh_token: str
    scope: str | None


# output models


class GrantType(StrEnum):
    AUTHORIZATION_CODE = "authorization_code"
    CLIENT_CREDENTIALS = "client_credentials"
    REFRESH_TOKEN = "refresh_token"

    # TODO: Add support for other grant types


class TokenType(StrEnum):
    BEARER = "Bearer"


class Token(BaseModel):
    access_token: str
    refresh_token: str | None
    token_type: Literal["Bearer"]
    expires_in: int
    expires_at: datetime
    scope: str | None
