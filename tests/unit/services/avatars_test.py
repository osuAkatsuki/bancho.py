from __future__ import annotations

from pathlib import Path

import app.services.avatars as avatars

_PNG_DATA = b"\x89PNG\r\n\x1a\n" + b"image bytes" + b"\x49END\xae\x42\x60\x82"
_JPEG_DATA = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"image bytes"


async def test_avatars_service_writes_png_file(tmp_path: Path) -> None:
    service = avatars.AvatarsService(avatars_path=tmp_path)

    result = await service.upload_avatar(user_id=3, avatar_data=_PNG_DATA)

    assert result is avatars.AvatarUploadResultCode.UPLOADED
    assert (tmp_path / "3.png").read_bytes() == _PNG_DATA


async def test_avatars_service_writes_jpeg_file(tmp_path: Path) -> None:
    service = avatars.AvatarsService(avatars_path=tmp_path)

    result = await service.upload_avatar(user_id=3, avatar_data=_JPEG_DATA)

    assert result is avatars.AvatarUploadResultCode.UPLOADED
    assert (tmp_path / "3.jpeg").read_bytes() == _JPEG_DATA


async def test_avatars_service_removes_previous_avatars_of_other_types(
    tmp_path: Path,
) -> None:
    service = avatars.AvatarsService(avatars_path=tmp_path)
    (tmp_path / "3.jpg").write_bytes(b"an old avatar")

    result = await service.upload_avatar(user_id=3, avatar_data=_PNG_DATA)

    assert result is avatars.AvatarUploadResultCode.UPLOADED
    assert not (tmp_path / "3.jpg").exists()
    assert (tmp_path / "3.png").read_bytes() == _PNG_DATA


async def test_avatars_service_does_not_touch_other_players_avatars(
    tmp_path: Path,
) -> None:
    service = avatars.AvatarsService(avatars_path=tmp_path)
    (tmp_path / "4.png").write_bytes(b"another player's avatar")

    result = await service.upload_avatar(user_id=3, avatar_data=_PNG_DATA)

    assert result is avatars.AvatarUploadResultCode.UPLOADED
    assert (tmp_path / "4.png").read_bytes() == b"another player's avatar"


async def test_avatars_service_rejects_oversized_files(tmp_path: Path) -> None:
    service = avatars.AvatarsService(avatars_path=tmp_path)
    oversized_data = b"\x00" * (avatars.MAX_AVATAR_SIZE_BYTES + 1)

    result = await service.upload_avatar(user_id=3, avatar_data=oversized_data)

    assert result is avatars.AvatarUploadResultCode.FILE_TOO_LARGE
    assert list(tmp_path.iterdir()) == []


async def test_avatars_service_rejects_invalid_file_types(tmp_path: Path) -> None:
    service = avatars.AvatarsService(avatars_path=tmp_path)

    result = await service.upload_avatar(user_id=3, avatar_data=b"not an image")

    assert result is avatars.AvatarUploadResultCode.INVALID_FILE_TYPE
    assert list(tmp_path.iterdir()) == []
