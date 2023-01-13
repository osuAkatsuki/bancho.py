from __future__ import annotations

from datetime import datetime

from . import BaseModel


# input models


# output models


class Clan(BaseModel):
    id: int
    name: str
    tag: str
    owner: int
    created_at: datetime
