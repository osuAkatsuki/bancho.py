import asyncio
import importlib.metadata
import inspect
import io
import ipaddress
import os
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import types
import zipfile
from pathlib import Path
from typing import Any
from typing import AsyncGenerator
from typing import Callable
from typing import Optional
from typing import Sequence
from typing import Type
from typing import TypedDict
from typing import TypeVar
from typing import Union

import aiomysql
import cmyui
import dill as pickle
import pymysql
import requests
from cmyui.logging import Ansi
from cmyui.logging import log
from cmyui.logging import printc
from cmyui.logging import Rainbow
from cmyui.osu.replay import Keys
from cmyui.osu.replay import ReplayFrame

from constants.countries import country_codes
from objects import glob

__all__ = (
    # TODO: organize/sort these
    "get_press_times",
    "make_safe_name",
    "fetch_bot_name",
    "download_achievement_images",
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
    "_get_current_mysql_structure_version",
    "update_mysql_structure",
)

DATA_PATH = Path.cwd() / ".data"
ACHIEVEMENTS_ASSETS_PATH = DATA_PATH / "assets/medals/client"
DEBUG_HOOKS_PATH = Path.cwd() / "_testing/runtime.py"
OPPAI_PATH = Path.cwd() / "oppai-ng"
SQL_UPDATES_FILE = Path.cwd() / "ext/updates.sql"

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


async def fetch_bot_name(db_cursor: aiomysql.DictCursor) -> str:
    """Fetch the bot's name from the database, if available."""
    await db_cursor.execute("SELECT name " "FROM users " "WHERE id = 1")

    if db_cursor.rowcount == 0:
        log(
            "Couldn't find bot account in the database, "
            "defaulting to BanchoBot for their name.",
            Ansi.LYELLOW,
        )
        return "BanchoBot"

    return (await db_cursor.fetchone())["name"]


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
        log("Successfully saved all achievement images.", Ansi.LGREEN)
    else:
        # TODO: make the code safe in this state
        log("Failed to download achievement images.", Ansi.LRED)
        achievements_path.rmdir()


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


def _install_synchronous_excepthook() -> None:
    """Install a thin wrapper for sys.excepthook to catch gulag-related stuff."""
    real_excepthook = sys.excepthook  # backup

    def _excepthook(
        type_: Type[BaseException], value: BaseException, traceback: types.TracebackType
    ):
        if type_ is KeyboardInterrupt:
            print("\33[2K\r", end="Aborted startup.")
            return
        elif type_ is AttributeError and value.args[0].startswith(
            "module 'config' has no attribute"
        ):
            attr_name = value.args[0][34:-1]
            log(
                "gulag's config has been updated, and has "
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
            f"gulag v{glob.version!r} ran into an issue " "before starting up :(",
            Ansi.RED,
        )
        real_excepthook(type_, value, traceback)  # type: ignore

    sys.excepthook = _excepthook


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
        ::-1
    ]  # reverse for python-like stacktrace
    # ordering; puts the most recent
    # call closest to the command line


STRANGE_LOG_DIR = Path.cwd() / ".data/logs"


async def log_strange_occurrence(obj: object) -> None:
    if not glob.has_internet:  # requires internet connection
        return

    pickled_obj: bytes = pickle.dumps(obj)
    uploaded = False

    if glob.config.automatically_report_problems:
        # automatically reporting problems to cmyui's server
        async with glob.http_session.post(
            url="https://log.cmyui.xyz/",
            headers={
                "Gulag-Version": repr(glob.version),
                "Gulag-Domain": glob.config.domain,
            },
            data=pickled_obj,
        ) as resp:
            if resp.status == 200 and (await resp.read()) == b"ok":
                uploaded = True
                log("Logged strange occurrence to cmyui's server.", Ansi.LBLUE)
                log("Thank you for your participation! <3", Rainbow)
            else:
                log(
                    f"Autoupload to cmyui's server failed (HTTP {resp.status})",
                    Ansi.LRED,
                )

    if not uploaded:
        # log to a file locally, and prompt the user
        while True:
            log_file = STRANGE_LOG_DIR / f"strange_{secrets.token_hex(4)}.db"
            if not log_file.exists():
                break

        log_file.touch(exist_ok=False)
        log_file.write_bytes(pickled_obj)

        log("Logged strange occurrence to", Ansi.LYELLOW, end=" ")
        printc("/".join(log_file.parts[-4:]), Ansi.LBLUE)

        log(
            "Greatly appreciated if you could forward this to cmyui#0425 :)",
            Ansi.LYELLOW,
        )


def is_inet_address(addr: Union[tuple[str, int], str]) -> bool:
    """Check whether addr is of type tuple[str, int]."""
    return (
        isinstance(addr, tuple)
        and len(addr) == 2
        and isinstance(addr[0], str)
        and isinstance(addr[1], int)
    )


IPAddress = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]


class Geolocation(TypedDict):
    latitude: float
    longitude: float
    country: dict[str, Union[str, int]]


def fetch_geoloc_db(ip: IPAddress) -> Optional[Geolocation]:
    """Fetch geolocation data based on ip (using local db)."""
    if not glob.geoloc_db:
        return

    res = glob.geoloc_db.city(ip)

    if res.country.iso_code is not None:
        acronym = res.country.iso_code.lower()
    else:
        acronym = "XX"

    return {
        "latitude": res.location.latitude or 0.0,
        "longitude": res.location.longitude or 0.0,
        "country": {"acronym": acronym, "numeric": country_codes[acronym]},
    }


async def fetch_geoloc_web(ip: IPAddress) -> Optional[Geolocation]:
    """Fetch geolocation data based on ip (using ip-api)."""
    if not glob.has_internet:  # requires internet connection
        return

    url = f"http://ip-api.com/line/{ip}"

    async with glob.http_session.get(url) as resp:
        if not resp or resp.status != 200:
            log("Failed to get geoloc data: request failed.", Ansi.LRED)
            return

        status, *lines = (await resp.text()).split("\n")

        if status != "success":
            err_msg = lines[0]
            if err_msg == "invalid query":
                err_msg += f" ({url})"

            log(f"Failed to get geoloc data: {err_msg}.", Ansi.LRED)
            return

    acronym = lines[1].lower()

    return {
        "latitude": float(lines[6]),
        "longitude": float(lines[7]),
        "country": {"acronym": acronym, "numeric": country_codes[acronym]},
    }


T = TypeVar("T")


def pymysql_encode(
    conv: Callable[[Any, Optional[dict[object, object]]], str]
) -> Callable[[T], T]:
    """Decorator to allow for adding to pymysql's encoders."""

    def wrapper(cls: T) -> T:
        pymysql.converters.encoders[cls] = conv
        return cls

    return wrapper


def escape_enum(
    val: Any, _: Optional[dict[object, object]] = None
) -> str:  # used for ^
    return str(int(val))


def shutdown_signal_handler(signum: Union[int, signal.Signals]) -> None:
    """Handle a posix signal, flagging the server to shut down."""
    print("\x1b[2K", end="\r")  # remove ^C from window

    # TODO: handle SIGUSR1 for restarting

    if glob.shutting_down:
        return

    log(f"Received {signal.strsignal(signum)}", Ansi.LRED)

    glob.shutting_down = True


def _handle_fut_exception(fut: asyncio.Future) -> None:
    if not fut.cancelled():
        if exception := fut.exception():
            glob.loop.call_exception_handler(
                {
                    "message": "unhandled exception during loop shutdown",
                    "exception": exception,
                    "task": fut,
                }
            )


def _conn_finished_cb(task: asyncio.Task) -> None:
    if not task.cancelled():
        exc = task.exception()
        if exc is not None and not isinstance(exc, (SystemExit, KeyboardInterrupt)):
            loop = asyncio.get_running_loop()
            loop.default_exception_handler({"exception": exc})

    glob.ongoing_conns.remove(task)
    task.remove_done_callback(_conn_finished_cb)


async def await_ongoing_connections(timeout: float) -> None:
    log(
        f"-> Allowing up to {timeout:.2f} seconds for "
        f"{len(glob.ongoing_conns)} ongoing connection(s) to finish.",
        Ansi.LMAGENTA,
    )

    done, pending = await asyncio.wait(glob.ongoing_conns, timeout=timeout)

    for task in done:
        _handle_fut_exception(task)

    if pending:
        log(
            f"-> Awaital timeout - cancelling {len(pending)} pending connection(s).",
            Ansi.LRED,
        )

        for task in pending:
            task.cancel()

        await asyncio.gather(*pending, return_exceptions=True)

        for task in pending:
            _handle_fut_exception(task)


async def cancel_housekeeping_tasks() -> None:
    log(
        f"-> Cancelling {len(glob.housekeeping_tasks)} housekeeping tasks.",
        Ansi.LMAGENTA,
    )

    # cancel housekeeping tasks
    for task in glob.housekeeping_tasks:
        task.cancel()

    await asyncio.gather(*glob.housekeeping_tasks, return_exceptions=True)

    for task in glob.housekeeping_tasks:
        _handle_fut_exception(task)


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


def ensure_local_services_are_running() -> int:
    """Ensure all required services (mysql, redis) are running."""
    # NOTE: if you have any problems with this, please contact me
    # @cmyui#0425/cmyuiosu@gmail.com. i'm interested in knowing
    # how people are using the software so that i can keep it
    # in mind while developing new features & refactoring.

    if glob.config.mysql["host"] in ("localhost", "127.0.0.1", None):
        # sql server running locally, make sure it's running
        for service in ("mysqld", "mariadb"):
            if os.path.exists(f"/var/run/{service}/{service}.pid"):
                break
        else:
            # not found, try pgrep
            pgrep_exit_code = subprocess.call(
                ["pgrep", "mysqld"], stdout=subprocess.DEVNULL
            )
            if pgrep_exit_code != 0:
                log("Please start your mysqld server.", Ansi.LRED)
                return 1

    if not os.path.exists("/var/run/redis/redis-server.pid"):
        log("Please start your redis server.", Ansi.LRED)
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

    return 0


def ensure_dependencies_and_requirements() -> int:
    """Make sure all of gulag's dependencies are ready."""
    if not OPPAI_PATH.exists():
        log("No oppai-ng submodule found, attempting to clone.", Ansi.LMAGENTA)
        p = subprocess.Popen(
            args=["git", "submodule", "init"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if exit_code := p.wait():
            log("Failed to initialize git submodules.", Ansi.LRED)
            return exit_code

        p = subprocess.Popen(
            args=["git", "submodule", "update"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if exit_code := p.wait():
            log("Failed to update git submodules.", Ansi.LRED)
            return exit_code

    if not (OPPAI_PATH / "liboppai.so").exists():
        log("No oppai-ng library found, attempting to build.", Ansi.LMAGENTA)
        p = subprocess.Popen(
            args=["./libbuild"],
            cwd="oppai-ng",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if exit_code := p.wait():
            log("Failed to build oppai-ng automatically.", Ansi.LRED)
            return exit_code

    return 0


def setup_runtime_environment() -> None:
    """Configure the server's runtime environment."""
    # install a hook to catch exceptions outside of the event loop,
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
    if glob.config.advanced:
        log("running in advanced mode", Ansi.LRED)

    # running on root grants the software potentally dangerous and
    # unnecessary power over the operating system and is not advised.
    if os.geteuid() == 0:
        log(
            "It is not recommended to run gulag as root, " "especially in production..",
            Ansi.LYELLOW,
        )

        if glob.config.advanced:
            log(
                "The risk is even greater with features "
                "such as config.advanced enabled.",
                Ansi.LRED,
            )

    if not glob.has_internet:
        log(
            "Running in offline mode, some features " "will not be available.",
            Ansi.LRED,
        )


def create_config_from_default() -> None:
    """Create the default config from ext/config.sample.py"""
    shutil.copy("ext/config.sample.py", "config.py")

    log(
        "A config file has been generated, " "please configure it to your needs.",
        Ansi.LRED,
    )


async def _get_latest_dependency_versions() -> AsyncGenerator[
    tuple[str, cmyui.Version, cmyui.Version], None
]:
    """Return the current installed & latest version for each dependency."""
    with open("ext/requirements.txt") as f:
        dependencies = f.read().splitlines(keepends=False)

    for dependency in dependencies:
        current_ver_str = importlib.metadata.version(dependency)
        current_ver = cmyui.Version.from_str(current_ver_str)

        if not current_ver:
            # the module uses some more advanced (and often hard to parse)
            # versioning system, so we won't be able to report updates.
            continue

        # TODO: split up and do the requests asynchronously
        url = f"https://pypi.org/pypi/{dependency}/json"
        async with glob.http_session.get(url) as resp:
            if resp.status == 200 and (json := await resp.json()):
                latest_ver = cmyui.Version.from_str(json["info"]["version"])

                if not latest_ver:
                    # they've started using a more advanced versioning system.
                    continue

                yield (dependency, latest_ver, current_ver)
            else:
                yield (dependency, current_ver, current_ver)


async def check_for_dependency_updates() -> None:
    """Notify the developer of any dependency updates available."""
    updates_available = False

    async for module, current_ver, latest_ver in _get_latest_dependency_versions():
        if latest_ver > current_ver:
            updates_available = True
            log(
                f"{module} has an update available "
                f"[{current_ver!r} -> {latest_ver!r}]",
                Ansi.LMAGENTA,
            )

    if updates_available:
        log(
            "Python modules can be updated with "
            "`python3.9 -m pip install -U <modules>`.",
            Ansi.LMAGENTA,
        )


async def _get_current_mysql_structure_version() -> Optional[cmyui.Version]:
    """Get the last launched version of the server."""
    res = await glob.db.fetch(
        "SELECT ver_major, ver_minor, ver_micro "
        "FROM startups ORDER BY datetime DESC LIMIT 1",
        _dict=False,  # get tuple
    )

    if res:
        return cmyui.Version(*map(int, res))


async def update_mysql_structure() -> None:
    """Update the mysql structure, if it has changed."""
    if not (current_ver := await _get_current_mysql_structure_version()):
        return  # already up to date (server has never run before)

    latest_ver = glob.version

    if latest_ver == current_ver:
        return  # already up to date

    # version changed; there may be sql changes.
    content = SQL_UPDATES_FILE.read_text()

    queries = []
    q_lines = []

    update_ver = None

    for line in content.splitlines():
        if not line:
            continue

        if line.startswith("#"):
            # may be normal comment or new version
            if r_match := VERSION_RGX.fullmatch(line):
                update_ver = cmyui.Version.from_str(r_match["ver"])

            continue
        elif not update_ver:
            continue

        # we only need the updates between the
        # previous and new version of the server.
        if current_ver < update_ver <= latest_ver:
            if line.endswith(";"):
                if q_lines:
                    q_lines.append(line)
                    queries.append(" ".join(q_lines))
                    q_lines = []
                else:
                    queries.append(line)
            else:
                q_lines.append(line)

    if not queries:
        return

    log(
        "Updating mysql structure " f"(v{current_ver!r} -> v{latest_ver!r}).",
        Ansi.LMAGENTA,
    )

    updated = False

    # NOTE: this using a transaction is pretty pointless with mysql since
    # any structural changes to tables will implciticly commit the changes.
    # https://dev.mysql.com/doc/refman/5.7/en/implicit-commit.html
    async with glob.db.pool.acquire() as conn:
        async with conn.cursor() as db_cursor:
            await conn.begin()
            for query in queries:
                try:
                    await db_cursor.execute(query)
                except aiomysql.MySQLError:
                    await conn.rollback()
                    break
            else:
                # all queries ran
                # without problems.
                await conn.commit()
                updated = True

    if not updated:
        log(f"Failed: {query}", Ansi.GRAY)
        log(
            "SQL failed to update - unless you've been "
            "modifying sql and know what caused this, "
            "please please contact cmyui#0425.",
            Ansi.LRED,
        )

        raise KeyboardInterrupt
