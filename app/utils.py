from __future__ import annotations

import inspect
import io
import ipaddress
import os
import shutil
import socket
import subprocess
import sys
import types
import zipfile
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Optional
from typing import TypedDict
from typing import TypeVar

import orjson
import pymysql
import requests
from fastapi import status

import app.settings
from app.logging import Ansi
from app.logging import log
from app.logging import printc

__all__ = (
    # TODO: organize/sort these
    "make_safe_name",
    "download_achievement_images",
    "download_default_avatar",
    "seconds_readable",
    "check_connection",
    "processes_listening_on_unix_socket",
    "running_via_asgi_webserver",
    "_install_synchronous_excepthook",
    "get_appropriate_stacktrace",
    "is_valid_inet_address",
    "is_valid_unix_address",
    "pymysql_encode",
    "escape_enum",
    "ensure_supported_platform",
    "ensure_connected_services",
    "ensure_directory_structure",
    "ensure_dependencies_and_requirements",
    "setup_runtime_environment",
    "_install_debugging_hooks",
    "display_startup_dialog",
    "create_config_from_default",
    "orjson_serialize_to_str",
    "get_media_type",
    "has_jpeg_headers_and_trailers",
    "has_png_headers_and_trailers",
)

DATA_PATH = Path.cwd() / ".data"
ACHIEVEMENTS_ASSETS_PATH = DATA_PATH / "assets/medals/client"
DEFAULT_AVATAR_PATH = DATA_PATH / "avatars/default.jpg"
DEBUG_HOOKS_PATH = Path.cwd() / "_testing/runtime.py"


def make_safe_name(name: str) -> str:
    """Return a name safe for usage in sql."""
    return name.lower().replace(" ", "_")


def _download_achievement_images_mirror(achievements_path: Path) -> bool:
    """Download all used achievement images (using mirror's zip)."""

    # NOTE: this is currently disabled as there's
    #       not much benefit to maintaining it
    return False

    log("Downloading achievement images from mirror.", Ansi.LCYAN)
    resp = requests.get("https://cmyui.xyz/achievement_images.zip")

    if resp.status_code != status.HTTP_200_OK:
        log("Failed to fetch from mirror, trying osu! servers.", Ansi.LRED)
        return False

    with io.BytesIO(resp.content) as data:
        with zipfile.ZipFile(data) as myfile:
            myfile.extractall(achievements_path)

    return True


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
        resp = requests.get(f"https://assets.ppy.sh/medals/client/{ach}")
        if resp.status_code != 200:
            return False

        log(f"Saving achievement: {ach}", Ansi.LCYAN)
        (achievements_path / ach).write_bytes(resp.content)

    return True


def download_achievement_images(achievements_path: Path) -> None:
    """Download all used achievement images (using the best available source)."""
    # try using my cmyui.xyz mirror (zip file)
    downloaded = _download_achievement_images_mirror(achievements_path)

    if not downloaded:
        # as fallback, download individual files from osu!
        downloaded = _download_achievement_images_osu(achievements_path)

    if downloaded:
        log("Downloaded all achievement images.", Ansi.LGREEN)
    else:
        # TODO: make the code safe in this state
        log("Failed to download achievement images.", Ansi.LRED)
        achievements_path.rmdir()


def download_default_avatar(default_avatar_path: Path) -> None:
    """Download an avatar to use as the server's default."""
    resp = requests.get("https://i.cmyui.xyz/U24XBZw-4wjVME-JaEz3.png")

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


def check_connection(timeout: float = 1.0) -> bool:
    """Check for an active internet connection."""
    # attempt to connect to common dns servers
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        for addr in (
            "1.1.1.1",
            "1.0.0.1",  # cloudflare
            "8.8.8.8",
            "8.8.4.4",
        ):  # google
            try:
                sock.connect((addr, 53))
                return True
            except OSError:
                continue

    # all connections failed
    return False


def processes_listening_on_unix_socket(socket_path: str) -> int:
    """Return the number of processes currently listening on this socket."""
    with open("/proc/net/unix") as f:  # TODO: does this require root privs?
        unix_socket_data = f.read().splitlines(keepends=False)

    process_count = 0

    for line in unix_socket_data[1:]:
        # 0000000045fe59d0: 00000002 00000000 00010000 0005 01 17665 /tmp/bancho.sock
        tokens = line.split()

        # unused params
        # (
        #     kernel_table_slot_num,
        #     ref_count,
        #     protocol,
        #     flags,
        #     sock_type,
        #     sock_state,
        #     inode,
        # )  = tokens[0:7]

        # path may or may not be set
        if len(tokens) == 8 and tokens[7] == socket_path:
            process_count += 1

    return process_count


def running_via_asgi_webserver() -> bool:
    return any(map(sys.argv[0].endswith, ("hypercorn", "uvicorn")))


def _install_synchronous_excepthook() -> None:
    """Install a thin wrapper for sys.excepthook to catch bancho-related stuff."""
    real_excepthook = sys.excepthook  # backup

    def _excepthook(
        type_: type[BaseException],
        value: BaseException,
        traceback: Optional[types.TracebackType],
    ):
        if type_ is KeyboardInterrupt:
            print("\33[2K\r", end="Aborted startup.")
            return
        elif type_ is AttributeError and value.args[0].startswith(
            "module 'config' has no attribute",
        ):
            attr_name = value.args[0][34:-1]
            log(
                "bancho.py's config has been updated, and has "
                f"added a new `{attr_name}` attribute.",
                Ansi.LMAGENTA,
            )
            log(
                "Please refer to it's value & example in "
                "ext/config.sample.py for additional info.",
                Ansi.LCYAN,
            )
            return

        printc(
            f"bancho.py v{app.settings.VERSION} ran into an issue before starting up :(",
            Ansi.RED,
        )
        real_excepthook(type_, value, traceback)  # type: ignore

    sys.excepthook = _excepthook


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


def is_valid_inet_address(address: str) -> bool:
    """Check whether address is a valid ipv(4/6) address."""
    try:
        ipaddress.ip_address(address)
    except ValueError:
        return False
    else:
        return True


def is_valid_unix_address(address: str) -> bool:
    """Check whether address is a valid unix address."""
    return address.endswith(".sock")  # TODO: improve


T = TypeVar("T")


def pymysql_encode(
    conv: Callable[[Any, Optional[dict[object, object]]], str],
) -> Callable[[T], T]:
    """Decorator to allow for adding to pymysql's encoders."""

    def wrapper(cls: T) -> T:
        pymysql.converters.encoders[cls] = conv
        return cls

    return wrapper


def escape_enum(
    val: Any,
    _: Optional[dict[object, object]] = None,
) -> str:  # used for ^
    return str(int(val))


def ensure_supported_platform() -> int:
    """Ensure we're running on an appropriate platform for bancho.py."""
    if sys.platform != "linux":
        log("bancho.py currently only supports linux", Ansi.LRED)
        if sys.platform == "win32":
            log(
                "you could also try wsl(2), i'd recommend ubuntu 18.04 "
                "(i use it to test bancho.py)",
                Ansi.LBLUE,
            )
        return 1

    if sys.version_info < (3, 9):
        log(
            "bancho.py uses many modern python features, "
            "and the minimum python version is 3.9.",
            Ansi.LRED,
        )
        return 1

    return 0


def ensure_connected_services(timeout: float = 1.0) -> int:
    """Ensure connected service connections are functional and running."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        try:
            sock.connect((app.settings.DB_HOST, app.settings.DB_PORT))
        except OSError:
            log("Unable to connect to mysql server.", Ansi.LRED)
            return 1

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.connect((app.settings.REDIS_HOST, app.settings.REDIS_PORT))
        except OSError:
            log("Unable to connect to redis server.", Ansi.LRED)
            return 1

    return 0


def ensure_directory_structure() -> int:
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

    return 0


def setup_runtime_environment() -> None:
    """Configure the server's runtime environment."""
    # install a hook to catch exceptions outside the event loop,
    # which will handle various situations where the error details
    # can be cleared up for the developer; for example it will explain
    # that the config has been updated when an unknown attribute is
    # accessed, so the developer knows what to do immediately.
    _install_synchronous_excepthook()

    # we print utf-8 content quite often, so configure sys.stdout
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")


def _install_debugging_hooks() -> None:
    """Change internals to help with debugging & active development."""
    if DEBUG_HOOKS_PATH.exists():
        from _testing import runtime  # type: ignore

        runtime.setup()


def display_startup_dialog() -> None:
    """Print any general information or warnings to the console."""
    if app.settings.DEVELOPER_MODE:
        log("running in advanced mode", Ansi.LRED)
    if app.settings.DEBUG:
        log("running in debug mode", Ansi.LMAGENTA)

    # running on root grants the software potentally dangerous and
    # unnecessary power over the operating system and is not advised.
    if os.geteuid() == 0:
        log(
            "It is not recommended to run bancho.py as root, especially in production..",
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


def orjson_serialize_to_str(*args, **kwargs) -> str:
    return orjson.dumps(*args, **kwargs).decode()


def get_media_type(extension: str) -> Optional[str]:
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
        and data_view[-8] == b"\x49END\xae\x42\x60\x82"
    )
