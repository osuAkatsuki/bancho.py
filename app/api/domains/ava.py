""" ava: avatar server (for both ingame & external) """
from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter
from fastapi import Response
from fastapi.responses import FileResponse

import app.state
import app.utils

AVATARS_PATH = Path.cwd() / ".data/avatars"
DEFAULT_AVATAR = AVATARS_PATH / "default.jpg"

router = APIRouter(tags=["Avatars"])


@router.get("/favicon.ico")
async def get_favicon() -> Response:
    return FileResponse(DEFAULT_AVATAR, media_type="image/ico")


@router.get("/{user_id}.{extension}")
async def get_avatar(
    user_id: int,
    extension: Literal["jpg", "jpeg", "png"],
) -> Response:
    avatar_path = AVATARS_PATH / f"{user_id}.{extension}"

    if not avatar_path.exists():
        avatar_path = DEFAULT_AVATAR

    return FileResponse(
        avatar_path,
        media_type=app.utils.get_media_type(extension),  # type: ignore
    )


@router.get("/{user_id}")
async def get_avatar_osu(user_id: int) -> Response:
    for extension in ("jpg", "jpeg", "png"):
        avatar_path = AVATARS_PATH / f"{user_id}.{extension}"

        if avatar_path.exists():
            return FileResponse(
                avatar_path,
                media_type=app.utils.get_media_type(extension),  # type: ignore
            )

    return FileResponse(DEFAULT_AVATAR, media_type="image/jpeg")
