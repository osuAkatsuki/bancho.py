from __future__ import annotations

from typing import Optional

from fastapi import UploadFile

from app._typing import OsuClientGameModes
from app._typing import OsuClientModes


## create


async def create(
    player_id: Optional[int],
    osu_mode: OsuClientModes,
    game_mode: OsuClientGameModes,
    game_time: int,
    audio_time: int,
    culture: str,
    map_id: int,
    map_md5: str,
    exception: str,
    feedback: Optional[str],
    stacktrace: str,
    soft: bool,
    map_count: int,
    compatibility: bool,
    ram_used: int,
    osu_version: str,
    exe_hash: str,
    config: str,
    screenshot_file: Optional[UploadFile],
) -> None:
    # TODO: insert the error report into the database
    ...


## read

## update

## delete
