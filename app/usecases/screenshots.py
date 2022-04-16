from __future__ import annotations

import secrets
from pathlib import Path
from typing import Literal
from typing import Optional

from fastapi import UploadFile

import app.utils

SCREENSHOTS_PATH = Path.cwd() / ".data/ss"


async def create(screenshot_file: UploadFile) -> tuple[bool, bytes]:
    """Upload a screenshot, saving the file on disk and returning it's filename."""
    with memoryview(await screenshot_file.read()) as screenshot_view:  # type: ignore
        # png sizes: 1080p: ~300-800kB | 4k: ~1-2mB
        if len(screenshot_view) > (4 * 1024 * 1024):
            return False, b"Screenshot file too large."

        if app.utils.has_jpeg_headers_and_trailers(screenshot_view):
            extension = "jpeg"
        elif app.utils.has_png_headers_and_trailers(screenshot_view):
            extension = "png"
        else:
            return False, b"Invalid file type"

        while True:
            filename = f"{secrets.token_urlsafe(6)}.{extension}"
            ss_file = SCREENSHOTS_PATH / filename
            if not ss_file.exists():
                break

        with ss_file.open("wb") as f:
            f.write(screenshot_view)

    return True, filename.encode()


def fetch_file(
    screenshot_id: str,
    extension: Literal["jpg", "jpeg", "png"],
) -> Optional[Path]:
    """Fetch a screenshot file on disk."""
    screenshot_path = SCREENSHOTS_PATH / f"{screenshot_id}.{extension}"

    if screenshot_path.exists():
        return screenshot_path

    return None
