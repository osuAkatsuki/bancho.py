from __future__ import annotations

from pydantic import BaseModel
from pydantic import Field


class OsuBeatmapRequestForm(BaseModel):
    beatmap_filenames: list[str] = Field(..., alias="Filenames")
    beatmap_ids: list[int] = Field(..., alias="Ids")
