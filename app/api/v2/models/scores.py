from __future__ import annotations

from datetime import datetime

from . import BaseModel

# input models


# output models


class Score(BaseModel):
    id: int
    map_md5: str
    userid: int

    score: int
    pp: float
    acc: float
    max_combo: int
    mods: int

    n300: int
    n100: int
    n50: int
    nmiss: int
    ngeki: int
    nkatu: int

    grade: str
    status: int
    mode: int

    play_time: datetime
    time_elapsed: int
    perfect: bool


class ScoreBeatmap(BaseModel):
    """Beatmap info embedded in score listings."""

    id: int
    set_id: int
    md5: str
    status: int

    artist: str
    title: str
    version: str
    creator: str

    last_update: datetime
    total_length: int
    max_combo: int
    plays: int
    passes: int
    mode: int

    bpm: float
    cs: float
    ar: float
    od: float
    hp: float
    diff: float


class PlayerScore(BaseModel):
    """A player's score, including the beatmap it was set on."""

    id: int
    map_md5: str

    score: int
    pp: float
    acc: float
    max_combo: int
    mods: int

    n300: int
    n100: int
    n50: int
    nmiss: int
    ngeki: int
    nkatu: int

    grade: str
    status: int
    mode: int

    play_time: datetime
    time_elapsed: int
    perfect: bool

    beatmap: ScoreBeatmap | None


class ScorePlayer(BaseModel):
    """Player info embedded in map score listings."""

    id: int
    name: str
    country: str
    clan_id: int | None
    clan_name: str | None
    clan_tag: str | None


class ScoreDetail(Score):
    """A single score with its beatmap and player embedded."""

    beatmap: ScoreBeatmap
    player: ScorePlayer


class MapScore(BaseModel):
    """A score on a map's leaderboard, including who set it."""

    id: int
    map_md5: str

    score: int
    pp: float
    acc: float
    max_combo: int
    mods: int

    n300: int
    n100: int
    n50: int
    nmiss: int
    ngeki: int
    nkatu: int

    grade: str
    status: int
    mode: int

    play_time: datetime
    time_elapsed: int
    perfect: bool

    player: ScorePlayer
