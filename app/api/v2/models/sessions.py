from __future__ import annotations

from . import BaseModel

# input models


class LoginRequest(BaseModel):
    username: str
    password: str


# output models
