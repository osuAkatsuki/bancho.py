from __future__ import annotations

from datetime import datetime
from typing import Any
from typing import Mapping
from typing import Union
from uuid import UUID

from . import BaseModel

# input models


class SessionUpdate(BaseModel):
    expires_at: Union[datetime, None]


class LoginForm(BaseModel):
    username: str
    password: str


# output models


class Session(BaseModel):
    session_id: UUID
    player_id: int
    expires_at: datetime
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> Session:
        return cls(
            session_id=mapping["session_id"],
            player_id=mapping["player_id"],
            expires_at=mapping["expires_at"],
            created_at=mapping["created_at"],
            updated_at=mapping["updated_at"],
        )
