import inspect
import io
import re
import shutil
import socket
import sys
import zipfile
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Optional
from typing import Sequence
from typing import TypeVar
from typing import Union

import orjson
import pymysql
import requests
from cmyui.logging import Ansi
from cmyui.logging import log
from cmyui.osu.replay import Keys
from cmyui.osu.replay import ReplayFrame
from databases.core import Connection

import app.db_models

__all__ = (
    # TODO: organize/sort these
    "get_press_times",
    "make_safe_name",
    "fetch_bot_name",
    "download_achievement_images",
    "download_default_avatar",
    "seconds_readable",
    "check_connection",
    "running_via_asgi_webserver",
    "_install_synchronous_excepthook",
    "get_appropriate_stacktrace",
    "log_strange_occurrence",
    "is_inet_address",
    "Geolocation",
    "fetch_geoloc_db",
    "fetch_geoloc_web",
    "pymysql_encode",
    "escape_enum",
    "shutdown_signal_handler",
    "_handle_fut_exception",
    "_conn_finished_cb",
    "await_ongoing_connections",
    "cancel_housekeeping_tasks",
    "ensure_supported_platform",
    "ensure_local_services_are_running",
    "ensure_directory_structure",
    "ensure_dependencies_and_requirements",
    "setup_runtime_environment",
    "_install_debugging_hooks",
    "display_startup_dialog",
    "create_config_from_default",
    "_get_latest_dependency_versions",
    "check_for_dependency_updates",
    "_get_current_sql_structure_version",
    "run_sql_migrations",
    "orjson_serialize_to_str",
    "get_media_type",
)

DATA_PATH = Path.cwd() / ".data"
ACHIEVEMENTS_ASSETS_PATH = DATA_PATH / "assets/medals/client"
DEFAULT_AVATAR_PATH = DATA_PATH / "avatars/default.jpg"
DEBUG_HOOKS_PATH = Path.cwd() / "_testing/runtime.py"
OPPAI_PATH = Path.cwd() / "oppai-ng"
SQL_UPDATES_FILE = Path.cwd() / "migrations/migrations.sql"


VERSION_RGX = re.compile(r"^# v(?P<ver>\d+\.\d+\.\d+)$")

useful_keys = (Keys.M1, Keys.M2, Keys.K1, Keys.K2)


def get_press_times(frames: Sequence[ReplayFrame]) -> dict[int, list[int]]:
    """A very basic function to press times of an osu! replay.
    This is mostly only useful for taiko maps, since it
    doesn't take holds into account (taiko has none).

    In the future, we will make a version that can take
    account for the type of note that is being hit, for
    much more accurate and useful detection ability.
    """
    # TODO: remove negatives?
    press_times: dict[int, list[int]] = {key: [] for key in useful_keys}
    cumulative = {key: 0 for key in useful_keys}

    prev_frame = frames[0]

    for frame in frames[1:]:
        for key in useful_keys:
            if frame.keys & key:
                # key pressed, add to cumulative
                cumulative[key] += frame.delta
            elif prev_frame.keys & key:
                # key unpressed, add to press times
                press_times[key].append(cumulative[key])
                cumulative[key] = 0

        prev_frame = frame

    # return all keys with presses
    return {k: v for k, v in press_times.items() if v}


def make_safe_name(name: str) -> str:
    """Return a name safe for usage in sql."""
    return name.lower().replace(" ", "_")


async def fetch_bot_name(db_cursor: Connection) -> str:
    """Fetch the bot's name from the database, if available."""
    bot_name = await db_cursor.fetch_val(
        app.db_models.users.select(app.db_models.users.c.name).where(
            app.db_models.users.c.id == 1,
        ),
        column=0,
    )

    if not bot_name:
        log(
            "Couldn't find bot account in the database, "
            "defaulting to BanchoBot for their name.",
            Ansi.LYELLOW,
        )
        return "BanchoBot"

    return bot_name


def _download_achievement_images_mirror(achievements_path: Path) -> bool:
    """Download all used achievement images (using mirror's zip)."""
    log("Downloading achievement images from mirror.", Ansi.LCYAN)
    r = requests.get("https://cmyui.xyz/achievement_images.zip")

    if r.status_code != 200:
        log("Failed to fetch from mirror, trying osu! servers.", Ansi.LRED)
        return False

    with io.BytesIO(r.content) as data:
        with zipfile.ZipFile(data) as myfile:
            myfile.extractall(achievements_path)

    return True


def _download_achievement_images_osu(achievements_path: Path) -> bool:
    """Download all used achievement images (one by one, from osu!)."""
    achs: list[str] = []

    for res in ("", "@2x"):
        for gm in ("osu", "taiko", "fruits", "mania"):
            # only osu!std has 9 & 10 star pass/fc medals.
            for n in range(1, 1 + (10 if gm == "osu" else 8)):
                achs.append(f"{gm}-skill-pass-{n}{res}.png")
                achs.append(f"{gm}-skill-fc-{n}{res}.png")

        for n in (500, 750, 1000, 2000):
            achs.append(f"osu-combo-{n}{res}.png")

    log("Downloading achievement images from osu!.", Ansi.LCYAN)

    for ach in achs:
        r = requests.get(f"https://assets.ppy.sh/medals/client/{ach}")
        if r.status_code != 200:
            return False

        log(f"Saving achievement: {ach}", Ansi.LCYAN)
        (achievements_path / ach).write_bytes(r.content)

    return True


def download_achievement_images(achievements_path: Path) -> None:
    """Download all used achievement images (using best available source)."""
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
    r = requests.get("https://i.cmyui.xyz/U24XBZw-4wjVME-JaEz3.png")

    if r.status_code != 200:
        log("Failed to fetch default avatar.", Ansi.LRED)
        return

    log("Downloaded default avatar.", Ansi.LGREEN)
    default_avatar_path.write_bytes(r.content)


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
            except socket.error:
                continue

    # all connections failed
    return False


def running_via_asgi_webserver() -> bool:
    return any(map(sys.argv[0].endswith, ("hypercorn", "uvicorn")))


def get_appropriate_stacktrace() -> list[dict[str, Union[str, int, dict[str, str]]]]:
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
        for frame in stack[:idx]
    ][
        # reverse for python-like stacktrace
        # ordering; puts the most recent
        # call closest to the command line
        ::-1
    ]


STRANGE_LOG_DIR = Path.cwd() / ".data/logs"


def is_inet_address(addr: Union[tuple[str, int], str]) -> bool:
    """Check whether addr is of type tuple[str, int]."""
    return (
        isinstance(addr, tuple)
        and len(addr) == 2
        and isinstance(addr[0], str)
        and isinstance(addr[1], int)
    )


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
    """Ensure we're running on an appropriate platform for gulag."""
    if sys.platform != "linux":
        log("gulag currently only supports linux", Ansi.LRED)
        if sys.platform == "win32":
            log(
                "you could also try wsl(2), i'd recommend ubuntu 18.04 "
                "(i use it to test gulag)",
                Ansi.LBLUE,
            )
        return 1

    if sys.version_info < (3, 9):
        log(
            "gulag uses many modern python features, "
            "and the minimum python version is 3.9.",
            Ansi.LRED,
        )
        return 1

    return 0


# def ensure_local_services_are_running() -> int:
#     """Ensure all required services (mysql, redis) are running."""
#     # NOTE: if you have any problems with this, please contact me
#     # @cmyui#0425/cmyuiosu@gmail.com. i'm interested in knowing
#     # how people are using the software so that i can keep it
#     # in mind while developing new features & refactoring.

#     if glob.config.mysql["host"] in ("localhost", "127.0.0.1", None):
#         # sql server running locally, make sure it's running
#         for service in ("mysqld", "mariadb"):
#             if os.path.exists(f"/var/run/{service}/{service}.pid"):
#                 break
#         else:
#             # not found, try pgrep
#             pgrep_exit_code = subprocess.call(
#                 ["pgrep", "mysqld"],
#                 stdout=subprocess.DEVNULL,
#             )
#             if pgrep_exit_code != 0:
#                 log("Please start your mysqld server.", Ansi.LRED)
#                 return 1

#     if not os.path.exists("/var/run/redis/redis-server.pid"):
#         log("Please start your redis server.", Ansi.LRED)
#         return 1

#     return 0


# def ensure_directory_structure() -> int:
#     """Ensure the .data directory and git submodules are ready."""
#     # create /.data and its subdirectories.
#     DATA_PATH.mkdir(exist_ok=True)

#     for sub_dir in ("avatars", "logs", "osu", "osr", "ss"):
#         subdir = DATA_PATH / sub_dir
#         subdir.mkdir(exist_ok=True)

#     if not ACHIEVEMENTS_ASSETS_PATH.exists():
#         ACHIEVEMENTS_ASSETS_PATH.mkdir(parents=True)
#         download_achievement_images(ACHIEVEMENTS_ASSETS_PATH)

#     if not DEFAULT_AVATAR_PATH.exists():
#         download_default_avatar(DEFAULT_AVATAR_PATH)

#     return 0


# def ensure_dependencies_and_requirements() -> int:
#     """Make sure all of gulag's dependencies are ready."""
#     if not OPPAI_PATH.exists():
#         log("No oppai-ng submodule found, attempting to clone.", Ansi.LMAGENTA)
#         p = subprocess.Popen(
#             args=["git", "submodule", "init"],
#             stdout=subprocess.DEVNULL,
#             stderr=subprocess.DEVNULL,
#         )
#         if exit_code := p.wait():
#             log("Failed to initialize git submodules.", Ansi.LRED)
#             return exit_code

#         p = subprocess.Popen(
#             args=["git", "submodule", "update"],
#             stdout=subprocess.DEVNULL,
#             stderr=subprocess.DEVNULL,
#         )
#         if exit_code := p.wait():
#             log("Failed to update git submodules.", Ansi.LRED)
#             return exit_code

#     if not (OPPAI_PATH / "liboppai.so").exists():
#         log("No oppai-ng library found, attempting to build.", Ansi.LMAGENTA)
#         p = subprocess.Popen(
#             args=["./libbuild"],
#             cwd="oppai-ng",
#             stdout=subprocess.DEVNULL,
#             stderr=subprocess.DEVNULL,
#         )
#         if exit_code := p.wait():
#             log("Failed to build oppai-ng automatically.", Ansi.LRED)
#             return exit_code

#     return 0


def setup_runtime_environment() -> None:
    """Configure the server's runtime environment."""
    # we print utf-8 content quite often, so configure sys.stdout
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")


def _install_debugging_hooks() -> None:
    """Change internals to help with debugging & active development."""
    if DEBUG_HOOKS_PATH.exists():
        from _testing import runtime  # type: ignore

        runtime.setup()


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
