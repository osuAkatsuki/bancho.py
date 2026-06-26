from __future__ import annotations

from types import SimpleNamespace

import app.services.screenshots as screenshots


async def _record_strange_occurrence(obj: object) -> None:
    pass


async def test_screenshot_service_rejects_invalid_file_type(tmp_path) -> None:
    service = screenshots.ScreenshotService(
        screenshots_path=tmp_path,
        token_urlsafe=lambda _size: "token",
        log_strange_occurrence=_record_strange_occurrence,
    )

    result = await service.upload_screenshot(
        player=SimpleNamespace(),
        endpoint_version=1,
        screenshot_data=b"not an image",
    )

    assert result.code is screenshots.ScreenshotUploadResultCode.INVALID_FILE_TYPE
    assert list(tmp_path.iterdir()) == []


async def test_screenshot_service_writes_png_file(tmp_path) -> None:
    service = screenshots.ScreenshotService(
        screenshots_path=tmp_path,
        token_urlsafe=lambda _size: "token",
        log_strange_occurrence=_record_strange_occurrence,
    )
    png_data = b"\x89PNG\r\n\x1a\n" + b"image bytes" + b"\x49END\xae\x42\x60\x82"

    result = await service.upload_screenshot(
        player=SimpleNamespace(),
        endpoint_version=1,
        screenshot_data=png_data,
    )

    assert result == screenshots.ScreenshotUploadResult(
        code=screenshots.ScreenshotUploadResultCode.UPLOADED,
        filename="token.png",
    )
    assert (tmp_path / "token.png").read_bytes() == png_data
