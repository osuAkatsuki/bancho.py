from __future__ import annotations

from datetime import datetime
from typing import Literal
from typing import Optional

from . import BaseModel


# input models


# output models


class Token(BaseModel):
    access_token: str
    refresh_token: Optional[str]
    token_type: Literal["Bearer"]
    expires_in: int
    expires_at: str
    scope: str
