from __future__ import annotations

from typing import Any

bcrypt: dict[bytes, bytes] = {}  # {bcrypt: md5, ...}
beatmap: dict[str | int, Any] = {}  # {md5: map, id: map, ...}
beatmapset: dict[int, Any] = {}  # {bsid: map_set}
unsubmitted: set[str] = set()  # {md5, ...}
needs_update: set[str] = set()  # {md5, ...}
