from __future__ import annotations

from pydantic import ConfigDict
from pydantic import Field
from pydantic.json_schema import SkipJsonSchema

from app._typing import UNSET
from app._typing import _UnsetSentinel
from app.api.v2.common.parameters import GameModeParam

from . import BaseModel

# input models


class ProfileUpdate(BaseModel):
    """Fields the authenticated player may change about themselves;
    omitted fields default to UNSET and are left untouched. Only the
    userpage is nullable; null is rejected everywhere else."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    username: str | SkipJsonSchema[_UnsetSentinel] = Field(
        default_factory=lambda: UNSET,
    )
    country: str | SkipJsonSchema[_UnsetSentinel] = Field(
        default_factory=lambda: UNSET,
    )
    preferred_mode: GameModeParam | SkipJsonSchema[_UnsetSentinel] = Field(
        default_factory=lambda: UNSET,
    )
    userpage_content: str | None | SkipJsonSchema[_UnsetSentinel] = Field(
        default_factory=lambda: UNSET,
    )


class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str


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

    # Global & country ranks are calculated from the redis
    # leaderboards, rather than being stored in the database.
    # A rank of None means the player is unranked for the mode.
    rank: int | None
    country_rank: int | None


class SearchPlayer(BaseModel):
    id: int
    name: str
