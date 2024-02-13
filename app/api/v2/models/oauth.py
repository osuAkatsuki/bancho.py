from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from . import BaseModel

# input models


# output models


class GrantType(StrEnum):
    AUTHORIZATION_CODE = "authorization_code"
    CLIENT_CREDENTIALS = "client_credentials"

    # TODO: Add support for other grant types


class Token(BaseModel):
    access_token: str
    refresh_token: str | None
    token_type: Literal["Bearer"]
    expires_in: int
    expires_at: datetime
    scope: str
