from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import app.utils

MAX_AVATAR_SIZE_BYTES = 2 * 1024 * 1024

# every extension the avatar server may serve for a given user id
_SERVED_EXTENSIONS = ("png", "jpg", "gif", "jpeg", "jfif")


class AvatarUploadResultCode(StrEnum):
    UPLOADED = "uploaded"
    FILE_TOO_LARGE = "file_too_large"
    INVALID_FILE_TYPE = "invalid_file_type"


@dataclass(frozen=True)
class AvatarsService:
    avatars_path: Path

    async def upload_avatar(
        self,
        *,
        user_id: int,
        avatar_data: bytes,
    ) -> AvatarUploadResultCode:
        with memoryview(avatar_data) as avatar_view:
            if len(avatar_view) > MAX_AVATAR_SIZE_BYTES:
                return AvatarUploadResultCode.FILE_TOO_LARGE

            if app.utils.has_jpeg_headers_and_trailers(avatar_view):
                extension = "jpeg"
            elif app.utils.has_png_headers_and_trailers(avatar_view):
                extension = "png"
            else:
                return AvatarUploadResultCode.INVALID_FILE_TYPE

        # a previous avatar may exist under a different extension, and the
        # avatar server picks the first extension it finds for a user id
        for served_extension in _SERVED_EXTENSIONS:
            if served_extension != extension:
                (self.avatars_path / f"{user_id}.{served_extension}").unlink(
                    missing_ok=True,
                )

        (self.avatars_path / f"{user_id}.{extension}").write_bytes(avatar_data)
        return AvatarUploadResultCode.UPLOADED
