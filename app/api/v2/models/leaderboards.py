from __future__ import annotations

from . import BaseModel

# input models


# output models


class LeaderboardEntry(BaseModel):
    # Ranks are calculated from the requested page & sort
    # order, rather than being stored in the database.
    rank: int

    player_id: int
    name: str
    country: str
    clan_id: int | None
    clan_name: str | None
    clan_tag: str | None

    tscore: int
    rscore: int
    pp: int
    acc: float
    plays: int
    playtime: int
    max_combo: int

    xh_count: int
    x_count: int
    sh_count: int
    s_count: int
    a_count: int
