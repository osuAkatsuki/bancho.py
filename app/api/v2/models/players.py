from __future__ import annotations

from datetime import datetime
from typing import Literal
from typing import Optional

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

    custom_badge_name: Optional[str]
    custom_badge_icon: Optional[str]

    userpage_content: Optional[str]


# Should use map from /models/maps.py when merged
class Map(BaseModel):
    server: Literal["osu!", "private"]
    id: int
    set_id: int
    status: int
    md5: str
    artist: str
    title: str
    version: str
    creator: str
    filename: str
    last_update: datetime
    total_length: int
    max_combo: int
    frozen: bool
    plays: int
    passes: int
    mode: int
    bpm: float
    cs: float
    ar: float
    od: float
    hp: float
    diff: float


class IngamePlayerStatus(BaseModel):
    action: int
    info_text: str
    mode: int
    mods: int
    beatmap: Optional[Map]


class OfflinePlayerStatus(BaseModel):
    online: bool
    last_seen: Optional[int]


class OnlinePlayerStatus(BaseModel):
    online: bool
    login_time: Optional[int]

    status: Optional[IngamePlayerStatus]
