from __future__ import annotations

from pydantic import BaseModel


class OsuBeatmapRequestForm(BaseModel):
    Filenames: list[str]
    Ids: list[int]
