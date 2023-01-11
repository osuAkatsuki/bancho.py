from __future__ import annotations

from datetime import datetime
from typing import Optional

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
    nkatu: int

    grade: str
    status: int
    mode: int

    play_time: datetime
    time_elapsed: int
    perfect: bool
