from __future__ import annotations

from . import BaseModel

# input models


# output models


class Player(BaseModel):
    id: int
    name: str
    safe_name: str

    priv: int
    country: str
    silence_end: int
    donor_end: int
    creation_time: int
    latest_activity: int

    clan_id: int
    clan_priv: int

    preferred_mode: int
    play_style: int

    custom_badge_name: str | None
    custom_badge_icon: str | None

    userpage_content: str | None


class PlayerStatus(BaseModel):
    login_time: int
    action: int
    info_text: str
    mode: int
    mods: int
    beatmap_id: int


class PlayerStats(BaseModel):
    id: int
    mode: int
    tscore: int
    rscore: int
    pp: float
    plays: int
    playtime: int
    acc: float
    max_combo: int
    total_hits: int
    replay_views: int
    xh_count: int
    x_count: int
    sh_count: int
    s_count: int
    a_count: int
