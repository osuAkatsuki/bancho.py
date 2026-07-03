from __future__ import annotations

from . import BaseModel

# input models


class RegistrationRequest(BaseModel):
    username: str
    email: str
    password: str
    captcha_token: str | None = None


# output models
