from __future__ import annotations

import secrets
from pathlib import Path as SystemPath

from fastapi import status
from fastapi.datastructures import UploadFile
from fastapi.param_functions import Depends
from fastapi.param_functions import File
from fastapi.param_functions import Form
from fastapi.responses import Response
from fastapi.routing import APIRouter

import app.state
import app.utils
from app.api.web.authentication import authenticate_player_session
from app.logging import log
from app.objects.player import Player

SCREENSHOTS_PATH = SystemPath.cwd() / ".data/ss"

router = APIRouter()


@router.post("/osu-screenshot.php")
async def osuScreenshot(
    player: Player = Depends(authenticate_player_session(Form, "u", "p")),
    endpoint_version: int = Form(..., alias="v"),
    screenshot_file: UploadFile = File(..., alias="ss"),
) -> Response:
    with memoryview(await screenshot_file.read()) as screenshot_view:
        # png sizes: 1080p: ~300-800kB | 4k: ~1-2mB
        if len(screenshot_view) > (4 * 1024 * 1024):
            return Response(
                content=b"Screenshot file too large.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if endpoint_version != 1:
            await app.state.services.log_strange_occurrence(
                f"Incorrect endpoint version (/web/osu-screenshot.php v{endpoint_version})",
            )

        if app.utils.has_jpeg_headers_and_trailers(screenshot_view):
            extension = "jpeg"
        elif app.utils.has_png_headers_and_trailers(screenshot_view):
            extension = "png"
        else:
            return Response(
                content=b"Invalid file type",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        while True:
            filename = f"{secrets.token_urlsafe(6)}.{extension}"
            ss_file = SCREENSHOTS_PATH / filename
            if not ss_file.exists():
                break

        with ss_file.open("wb") as f:
            f.write(screenshot_view)

    log(f"{player} uploaded {filename}.")
    return Response(filename.encode())
