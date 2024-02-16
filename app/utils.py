from __future__ import annotations

import ctypes
import inspect
import os
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any
from typing import TypedDict
from typing import TypeVar

import httpx
import orjson
import pymysql

import app.settings
from app.logging import Ansi
from app.logging import log

T = TypeVar("T")


DATA_PATH = Path.cwd() / ".data"
ACHIEVEMENTS_ASSETS_PATH = DATA_PATH / "assets/medals/client"
DEFAULT_AVATAR_PATH = DATA_PATH / "avatars/default.jpg"
DEBUG_HOOKS_PATH = Path.cwd() / "_testing/runtime.py"


def make_safe_name(name: str) -> str:
    """Return a name safe for usage in sql."""
    return name.lower().replace(" ", "_")


def _download_achievement_images_osu(achievements_path: Path) -> bool:
    """Download all used achievement images (one by one, from osu!)."""
    achs: list[str] = []

    for resolution in ("", "@2x"):
        for mode in ("osu", "taiko", "fruits", "mania"):
            # only osu!std has 9 & 10 star pass/fc medals.
            for star_rating in range(1, 1 + (10 if mode == "osu" else 8)):
                achs.append(f"{mode}-skill-pass-{star_rating}{resolution}.png")
                achs.append(f"{mode}-skill-fc-{star_rating}{resolution}.png")

        for combo in (500, 750, 1000, 2000):
            achs.append(f"osu-combo-{combo}{resolution}.png")

        for mod in (
            "suddendeath",
            "hidden",
            "perfect",
            "hardrock",
            "doubletime",
            "flashlight",
            "easy",
            "nofail",
            "nightcore",
            "halftime",
            "spunout",
        ):
            achs.append(f"all-intro-{mod}{resolution}.png")

    log("Downloading achievement images from osu!.", Ansi.LCYAN)

    for ach in achs:
        resp = httpx.get(f"https://assets.ppy.sh/medals/client/{ach}")
        if resp.status_code != 200:
            return False

        log(f"Saving achievement: {ach}", Ansi.LCYAN)
        (achievements_path / ach).write_bytes(resp.content)

    return True


def download_achievement_images(achievements_path: Path) -> None:
    """Download all used achievement images (using the best available source)."""

    # download individual files from the official osu! servers
    downloaded = _download_achievement_images_osu(achievements_path)

    if downloaded:
        log("Downloaded all achievement images.", Ansi.LGREEN)
    else:
        # TODO: make the code safe in this state
        log("Failed to download achievement images.", Ansi.LRED)
        achievements_path.rmdir()

        # allow passthrough (don't hard crash) as the server will
        # _mostly_ work in this state.


def download_default_avatar(default_avatar_path: Path) -> None:
    """Download an avatar to use as the server's default."""
    resp = httpx.get("https://i.cmyui.xyz/U24XBZw-4wjVME-JaEz3.png")

    if resp.status_code != 200:
        log("Failed to fetch default avatar.", Ansi.LRED)
        return

    log("Downloaded default avatar.", Ansi.LGREEN)
    default_avatar_path.write_bytes(resp.content)


def seconds_readable(seconds: int) -> str:
    """Turn seconds as an int into 'DD:HH:MM:SS'."""
    r: list[str] = []

    days, seconds = divmod(seconds, 60 * 60 * 24)
    if days:
        r.append(f"{days:02d}")

    hours, seconds = divmod(seconds, 60 * 60)
    if hours:
        r.append(f"{hours:02d}")

    minutes, seconds = divmod(seconds, 60)
    r.append(f"{minutes:02d}")

    r.append(f"{seconds % 60:02d}")
    return ":".join(r)


class FrameInfo(TypedDict):
    function: str
    filename: str
    lineno: int
    charno: int
    locals: dict[str, str]


def get_appropriate_stacktrace() -> list[FrameInfo]:
    """Return information of all frames related to cmyui_pkg and below."""
    stack = inspect.stack()[1:]
    for idx, frame in enumerate(stack):
        if frame.function == "run":
            break
    else:
        raise Exception

    return [
        {
            "function": frame.function,
            "filename": Path(frame.filename).name,
            "lineno": frame.lineno,
            "charno": frame.index or 0,
            "locals": {k: repr(v) for k, v in frame.frame.f_locals.items()},
        }
        # reverse for python-like stacktrace
        # ordering; puts the most recent
        # call closest to the command line
        for frame in reversed(stack[:idx])
    ]


def pymysql_encode(
    conv: Callable[[Any, dict[object, object] | None], str],
) -> Callable[[type[T]], type[T]]:
    """Decorator to allow for adding to pymysql's encoders."""

    def wrapper(cls: type[T]) -> type[T]:
        pymysql.converters.encoders[cls] = conv
        return cls

    return wrapper


def escape_enum(
    val: Any,
    _: dict[object, object] | None = None,
) -> str:  # used for ^
    return str(int(val))


def ensure_supported_platform() -> None:
    """Ensure we're running on an appropriate platform for bancho.py."""
    if sys.version_info < (3, 11):
        log(
            "bancho.py uses many modern python features, "
            "and the minimum python version is 3.11.",
            Ansi.LRED,
        )
        raise SystemExit(1)


def ensure_directory_structure() -> None:
    """Ensure the .data directory and git submodules are ready."""
    # create /.data and its subdirectories.
    DATA_PATH.mkdir(exist_ok=True)

    for sub_dir in ("avatars", "logs", "osu", "osr", "ss"):
        subdir = DATA_PATH / sub_dir
        subdir.mkdir(exist_ok=True)

    if not ACHIEVEMENTS_ASSETS_PATH.exists():
        ACHIEVEMENTS_ASSETS_PATH.mkdir(parents=True)
        download_achievement_images(ACHIEVEMENTS_ASSETS_PATH)

    if not DEFAULT_AVATAR_PATH.exists():
        download_default_avatar(DEFAULT_AVATAR_PATH)


def is_running_as_admin() -> bool:
    try:
        return os.geteuid() == 0  # type: ignore[attr-defined, no-any-return, unused-ignore]
    except AttributeError:
        pass

    try:
        return ctypes.windll.shell32.IsUserAnAdmin() == 1  # type: ignore[attr-defined, no-any-return, unused-ignore]
    except AttributeError:
        raise Exception(
            f"{sys.platform} is not currently supported on bancho.py, please create a github issue!",
        )


def display_startup_dialog() -> None:
    """Print any general information or warnings to the console."""
    if app.settings.DEVELOPER_MODE:
        log("running in advanced mode", Ansi.LRED)
    if app.settings.DEBUG:
        log("running in debug mode", Ansi.LMAGENTA)

    # running on root/admin grants the software potentally dangerous and
    # unnecessary power over the operating system and is not advised.
    if is_running_as_admin():
        log(
            "It is not recommended to run bancho.py as root/admin, especially in production..",
            Ansi.LYELLOW,
        )

        if app.settings.DEVELOPER_MODE:
            log(
                "The risk is even greater with features "
                "such as config.advanced enabled.",
                Ansi.LRED,
            )


def create_config_from_default() -> None:
    """Create the default config from ext/config.sample.py"""
    shutil.copy("ext/config.sample.py", "config.py")


def orjson_serialize_to_str(*args: Any, **kwargs: Any) -> str:
    return orjson.dumps(*args, **kwargs).decode()


def get_media_type(extension: str) -> str | None:
    if extension in ("jpg", "jpeg"):
        return "image/jpeg"
    elif extension == "png":
        return "image/png"

    # return none, fastapi will attempt to figure it out
    return None


def has_jpeg_headers_and_trailers(data_view: memoryview) -> bool:
    return data_view[:4] == b"\xff\xd8\xff\xe0" and data_view[6:11] == b"JFIF\x00"


def has_png_headers_and_trailers(data_view: memoryview) -> bool:
    return (
        data_view[:8] == b"\x89PNG\r\n\x1a\n"
        and data_view[-8:] == b"\x49END\xae\x42\x60\x82"
    )
