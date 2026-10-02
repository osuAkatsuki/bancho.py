from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.objects.beatmap import Beatmap
    from app.objects.beatmap import BeatmapSet


@dataclass
class ApplicationCaches:
    """Mutable caches owned by one application instance."""

    passwords: dict[bytes, bytes] = field(default_factory=dict)
    beatmaps: dict[str | int, Beatmap] = field(default_factory=dict)
    beatmapsets: dict[int, BeatmapSet] = field(default_factory=dict)
    unsubmitted: set[str] = field(default_factory=set)
    needs_update: set[str] = field(default_factory=set)
