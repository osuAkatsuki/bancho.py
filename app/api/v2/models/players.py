from __future__ import annotations

from typing import List
from typing import Optional

from . import BaseModel


class Player(BaseModel):
    id: int
    name: str
    safe_name: str
    _email: str

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


class Players(BaseModel):
    players: List[Player]
    max_pages: int
    current_page: int
