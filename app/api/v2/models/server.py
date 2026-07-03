from __future__ import annotations

from . import BaseModel

# input models


# output models


class ServerStats(BaseModel):
    online_players: int
    total_players: int


class ServerMeta(BaseModel):
    discord_invite: str | None
