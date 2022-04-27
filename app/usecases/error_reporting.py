## create
from __future__ import annotations

from typing import Optional

from fastapi import UploadFile

from app import repositories
from app._typing import OsuClientGameModes
from app._typing import OsuClientModes
from app.objects.player import Player


async def create(
    player: Optional[Player],
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
    await repositories.error_reporting.create(
        player.id if player else None,
        osu_mode,
        game_mode,
        game_time,
        audio_time,
        culture,
        map_id,
        map_md5,
        exception,
        feedback,
        stacktrace,
        soft,
        map_count,
        compatibility,
        ram_used,
        osu_version,
        exe_hash,
        config,
        screenshot_file,
    )


## read


async def fetch() -> None:
    ...


async def fetch_all() -> None:
    ...


## update

## delete
