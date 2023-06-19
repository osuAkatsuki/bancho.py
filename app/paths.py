from __future__ import annotations

import os
from pathlib import Path

from upath import UPath

DATA_PATH = (
    UPath(path)
    if (path := os.environ.get("DATA_PATH"))
    else (UPath(Path.cwd()) / ".data")
)

BEATMAPS_PATH = (
    UPath(path) if (path := os.environ.get("BEATMAPS_PATH")) else (DATA_PATH / "osu")
)
REPLAYS_PATH = (
    UPath(path) if (path := os.environ.get("REPLAYS_PATH")) else (DATA_PATH / "osr")
)
SCREENSHOTS_PATH = (
    UPath(path) if (path := os.environ.get("SCREENSHOTS_PATH")) else (DATA_PATH / "ss")
)
AVATARS_PATH = (
    UPath(path) if (path := os.environ.get("AVATARS_PATH")) else (DATA_PATH / "avatars")
)
ASSETS_PATH = (
    UPath(path) if (path := os.environ.get("ASSETS_PATH")) else (DATA_PATH / "assets")
)
LOGS_PATH = (
    UPath(path) if (path := os.environ.get("LOGS_PATH")) else (DATA_PATH / "logs")
)

ACHIEVEMENTS_ASSETS_PATH = ASSETS_PATH / "medals" / "client"
DEFAULT_AVATAR_PATH = AVATARS_PATH / "default.jpg"
