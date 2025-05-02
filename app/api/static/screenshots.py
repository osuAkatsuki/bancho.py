from __future__ import annotations

from pathlib import Path as SystemPath
from typing import Literal

from fastapi import status
from fastapi.param_functions import Path
from fastapi.responses import FileResponse
from fastapi.responses import ORJSONResponse
from fastapi.responses import Response
from fastapi.routing import APIRouter

SCREENSHOTS_PATH = SystemPath.cwd() / ".data/ss"


router = APIRouter()


@router.get("/{screenshot_id}.{extension}")
async def get_screenshot(
    screenshot_id: str = Path(..., pattern=r"[a-zA-Z0-9-_]{8}"),
    extension: Literal["jpg", "jpeg", "png"] = Path(...),
) -> Response:
    """Serve a screenshot from the server, by filename."""
    screenshot_path = SCREENSHOTS_PATH / f"{screenshot_id}.{extension}"

    if not screenshot_path.exists():
        return ORJSONResponse(
            content={"status": "Screenshot not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if extension in ("jpg", "jpeg"):
        media_type = "image/jpeg"
    elif extension == "png":
        media_type = "image/png"
    else:
        media_type = None

    return FileResponse(
        path=screenshot_path,
        media_type=media_type,
    )
