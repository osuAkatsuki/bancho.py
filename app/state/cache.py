from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.objects.beatmap import Beatmap
    from app.objects.beatmap import BeatmapSet


bcrypt: dict[bytes, bytes] = {}  # {bcrypt: md5, ...}
beatmap: dict[str | int, Beatmap] = {}  # {md5: map, id: map, ...}
beatmapset: dict[int, BeatmapSet] = {}  # {bsid: map_set}
unsubmitted: set[str] = set()  # {md5, ...}
needs_update: set[str] = set()  # {md5, ...}
