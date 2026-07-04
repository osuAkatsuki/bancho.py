from __future__ import annotations

from datetime import datetime

from . import BaseModel

# input models


# output models


class Map(BaseModel):
    id: int
    server: str
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


class MostPlayedMap(BaseModel):
    id: int
    set_id: int
    md5: str
    status: int
    artist: str
    title: str
    version: str
    creator: str

    # the number of times the player has played the map
    plays: int


class MapRating(BaseModel):
    average: float | None
    count: int
