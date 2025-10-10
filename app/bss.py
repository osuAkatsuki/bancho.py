from __future__ import annotations

import hashlib
import io
import statistics
import zipfile
from datetime import datetime
from zipfile import ZipFile
from zipfile import ZipInfo

from osz2 import File  # type: ignore[import-untyped]
from slider import Beatmap  # type: ignore[import-untyped]

video_file_extensions = (
    ".wmv",
    ".flv",
    ".mp4",
    ".avi",
    ".m4v",
    ".mpg",
    ".mov",
    ".webm",
    ".mkv",
    ".ogv",
    ".mpeg",
    ".3gp",
)


def osz_to_files(osz_data: bytes) -> list[File]:
    """Extract files from an .osz package into osz2.File objects"""
    with ZipFile(io.BytesIO(osz_data)) as zip_file:
        files = []

        for info in zip_file.infolist():
            content = zip_file.read(info.filename)
            content_hash = hashlib.md5(content).digest()

            file = File(
                filename=info.filename,
                content=content,
                offset=info.header_offset,
                size=info.file_size,
                hash=content_hash,
                date_created=datetime(*info.date_time),
                date_modified=datetime(*info.date_time),
            )
            files.append(file)

    return files


def maximum_beatmap_length(beatmaps: list[Beatmap]) -> int:
    """Retrieve the maximum total length of all beatmaps in milliseconds"""
    if not beatmaps:
        return 0

    return max(calculate_beatmap_total_length(beatmap) for beatmap in beatmaps)


def calculate_beatmap_total_length(beatmap: Beatmap) -> int:
    """Calculate the total length of a beatmap from its hit objects"""
    hit_objects = beatmap.hit_objects()

    if len(hit_objects) <= 1:
        return 0

    last_object = int(hit_objects[-1].time.total_seconds() * 1000)
    first_object = int(hit_objects[0].time.total_seconds() * 1000)
    return last_object - first_object


def create_osz_package(files: list[File]) -> bytes:
    """Create an .osz package from a list of files"""
    buffer = io.BytesIO()
    osz = ZipFile(buffer, "w", zipfile.ZIP_DEFLATED)

    for file in files:
        # Create ZipInfo to set file metadata
        zip_info = ZipInfo(filename=file.filename)
        zip_info.compress_type = zipfile.ZIP_DEFLATED
        zip_info.date_time = file.date_modified.timetuple()[:6]
        osz.writestr(zip_info, file.content)

    osz.close()
    result = buffer.getvalue()

    del buffer
    del osz
    return result


def calculate_size_limit(beatmap_length: int) -> int:
    # The file size limit is 10MB plus an additional 10MB for
    # every minute of beatmap length, and it caps at 100MB.
    return int(min(10_000_000 + (10_000_000 * (beatmap_length / 60)), 100_000_000))


def calculate_beatmap_median_bpm(beatmap: Beatmap) -> float:
    """Calculate the median BPM of a beatmap from its timing points"""
    bpm_values = [p.bpm for p in beatmap.timing_points if p.bpm]

    if not bpm_values:
        return 0.0

    return float(statistics.median(bpm_values))


def calculate_osz_size(files: list[File]) -> int:
    """Calculate the size of an .osz package from a list of files"""
    return len(create_osz_package(files))
