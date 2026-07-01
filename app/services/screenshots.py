from __future__ import annotations

from collections.abc import Awaitable
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import app.utils
from app.logging import log
from app.objects.player import Player


class ScreenshotUploadResultCode(StrEnum):
    UPLOADED = "uploaded"
    FILE_TOO_LARGE = "file_too_large"
    INVALID_FILE_TYPE = "invalid_file_type"


@dataclass(frozen=True)
class ScreenshotUploadResult:
    code: ScreenshotUploadResultCode
    filename: str | None = None


@dataclass(frozen=True)
class ScreenshotService:
    screenshots_path: Path
    token_urlsafe: Callable[[int], str]
    log_strange_occurrence: Callable[[object], Awaitable[None]]

    async def upload_screenshot(
        self,
        *,
        player: Player,
        endpoint_version: int,
        screenshot_data: bytes,
    ) -> ScreenshotUploadResult:
        with memoryview(screenshot_data) as screenshot_view:
            # png sizes: 1080p: ~300-800kB | 4k: ~1-2mB
            if len(screenshot_view) > (4 * 1024 * 1024):
                return ScreenshotUploadResult(
                    code=ScreenshotUploadResultCode.FILE_TOO_LARGE,
                )

            if endpoint_version != 1:
                await self.log_strange_occurrence(
                    "Incorrect endpoint version "
                    f"(/web/osu-screenshot.php v{endpoint_version})",
                )

            if app.utils.has_jpeg_headers_and_trailers(screenshot_view):
                extension = "jpeg"
            elif app.utils.has_png_headers_and_trailers(screenshot_view):
                extension = "png"
            else:
                return ScreenshotUploadResult(
                    code=ScreenshotUploadResultCode.INVALID_FILE_TYPE,
                )

        while True:
            filename = f"{self.token_urlsafe(6)}.{extension}"
            screenshot_path = self.screenshots_path / filename
            if not screenshot_path.exists():
                break

        with screenshot_path.open("wb") as screenshot_file:
            screenshot_file.write(screenshot_data)

        log(f"{player} uploaded {filename}.")
        return ScreenshotUploadResult(
            code=ScreenshotUploadResultCode.UPLOADED,
            filename=filename,
        )
