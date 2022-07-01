from __future__ import annotations

import asyncio
import ipaddress
import logging
import pickle
import re
import secrets
from pathlib import Path
from typing import AsyncGenerator
from typing import AsyncIterator
from typing import Mapping
from typing import MutableMapping
from typing import Optional
from typing import TYPE_CHECKING

import aioredis
import databases
import datadog as datadog_module
import datadog.threadstats.base as datadog_client
import geoip2.database
import pymysql

import app.settings
import app.state
from app._typing import IPAddress
from app.logging import ansi_rgb_rainbow

if TYPE_CHECKING:
    import aiohttp
    import databases.core


STRANGE_LOG_DIR = Path.cwd() / ".data/logs"
GEOLOC_DB_FILE = Path.cwd() / "ext/GeoLite2-City.mmdb"

VERSION_RGX = re.compile(r"^# v(?P<ver>\d+\.\d+\.\d+)$")
SQL_UPDATES_FILE = Path.cwd() / "migrations/migrations.sql"


""" session objects """

http_client: aiohttp.ClientSession
database = databases.Database(app.settings.DB_DSN)
redis: aioredis.Redis = aioredis.from_url(app.settings.REDIS_DSN)

geoloc_db: Optional[geoip2.database.Reader] = None
if GEOLOC_DB_FILE.exists():
    geoloc_db = geoip2.database.Reader(GEOLOC_DB_FILE)

datadog: Optional[datadog_client.ThreadStats] = None
if str(app.settings.DATADOG_API_KEY) and str(app.settings.DATADOG_APP_KEY):
    datadog_module.initialize(
        api_key=str(app.settings.DATADOG_API_KEY),
        app_key=str(app.settings.DATADOG_APP_KEY),
    )
    datadog = datadog_client.ThreadStats()

ip_resolver: IPResolver

housekeeping_tasks: list[asyncio.Task] = []

""" session usecases """


class IPResolver:
    def __init__(self) -> None:
        self.cache: MutableMapping[str, IPAddress] = {}

    def get_ip(self, headers: Mapping[str, str]) -> IPAddress:
        """Resolve the IP address from the headers."""
        if (ip_str := headers.get("CF-Connecting-IP")) is None:
            forwards = headers["X-Forwarded-For"].split(",")

            if len(forwards) != 1:
                ip_str = forwards[0]
            else:
                ip_str = headers["X-Real-IP"]

        if (ip := self.cache.get(ip_str)) is None:
            ip = ipaddress.ip_address(ip_str)
            self.cache[ip_str] = ip

        return ip


async def log_strange_occurrence(obj: object) -> None:
    pickled_obj: bytes = pickle.dumps(obj)
    uploaded = False

    if app.settings.AUTOMATICALLY_REPORT_PROBLEMS:
        # automatically reporting problems to cmyui's server
        async with http_client.post(
            url="https://log.cmyui.xyz/",
            headers={
                "Bancho-Version": app.settings.VERSION,
                "Bancho-Domain": app.settings.DOMAIN,
            },
            data=pickled_obj,
        ) as resp:
            if resp.status == 200 and (await resp.read()) == b"ok":
                uploaded = True
                logging.info("Logged strange occurrence to cmyui's server.")
                logging.info(ansi_rgb_rainbow("Thank you for your participation! <3"))
            else:
                logging.error(
                    f"Failed to automatically report an exception to the bancho.py devs (HTTP {resp.status})",
                )

    if not uploaded:
        # log to a file locally, and prompt the user
        while True:
            log_file = STRANGE_LOG_DIR / f"strange_{secrets.token_hex(4)}.db"
            if not log_file.exists():
                break

        log_file.touch(exist_ok=False)
        log_file.write_bytes(pickled_obj)

        logging.warning(f"Logged strange occurrence to {'/'.join(log_file.parts[-4:])}")
        logging.warning(
            "Greatly appreciated if you could forward this to cmyui#0425 :)",
        )


# dependency management


class Version:
    def __init__(self, major: int, minor: int, micro: int) -> None:
        self.major = major
        self.minor = minor
        self.micro = micro

    def __repr__(self) -> str:
        return f"{self.major}.{self.minor}.{self.micro}"

    def __hash__(self) -> int:
        return self.as_tuple.__hash__()

    def __eq__(self, other: Version) -> bool:
        return self.as_tuple == other.as_tuple

    def __lt__(self, other: Version) -> bool:
        return self.as_tuple < other.as_tuple

    def __le__(self, other: Version) -> bool:
        return self.as_tuple <= other.as_tuple

    def __gt__(self, other: Version) -> bool:
        return self.as_tuple > other.as_tuple

    def __ge__(self, other: Version) -> bool:
        return self.as_tuple >= other.as_tuple

    @property
    def as_tuple(self) -> tuple[int, int, int]:
        return (self.major, self.minor, self.micro)

    @classmethod
    def from_str(cls, s: str) -> Optional[Version]:
        if len(split := s.split(".")) == 3:
            return cls(
                major=int(split[0]),
                minor=int(split[1]),
                micro=int(split[2]),
            )

        return None


async def _get_latest_dependency_versions() -> AsyncGenerator[
    tuple[str, Version, Version],
    None,
]:
    """Return the current installed & latest version for each dependency."""
    with open("requirements.txt") as f:
        dependencies = f.read().splitlines(keepends=False)

    # TODO: use asyncio.gather() to do all requests at once? or chunk them

    for dependency in dependencies:
        dependency_name, _, dependency_ver = dependency.partition("==")
        current_ver = Version.from_str(dependency_ver)

        if not current_ver:
            # the module uses some more advanced (and often hard to parse)
            # versioning system, so we won't be able to report updates.
            continue

        # TODO: split up and do the requests asynchronously
        url = f"https://pypi.org/pypi/{dependency_name}/json"
        async with http_client.get(url) as resp:
            if resp.status == 200 and (json := await resp.json()):
                latest_ver = Version.from_str(json["info"]["version"])

                if not latest_ver:
                    # they've started using a more advanced versioning system.
                    continue

                yield (dependency_name, latest_ver, current_ver)
            else:
                yield (dependency_name, current_ver, current_ver)


async def check_for_dependency_updates() -> None:
    """Notify the developer of any dependency updates available."""
    updates_available = False

    async for module, current_ver, latest_ver in _get_latest_dependency_versions():
        if latest_ver > current_ver:
            updates_available = True
            logging.info(
                f"{module} has an update available "
                f"[{current_ver!r} -> {latest_ver!r}]",
            )

    if updates_available:
        logging.info(
            "Python modules can be updated with "
            "`python3.9 -m pip install -U <modules>`.",
        )


# sql migrations


async def _get_current_sql_structure_version() -> Optional[Version]:
    """Get the last launched version of the server."""
    res = await app.state.services.database.fetch_one(
        "SELECT ver_major, ver_minor, ver_micro "
        "FROM startups ORDER BY datetime DESC LIMIT 1",
    )

    if res:
        return Version(*map(int, res))

    return None


async def run_sql_migrations() -> None:
    """Update the sql structure, if it has changed."""
    if not (current_ver := await _get_current_sql_structure_version()):
        return  # already up to date (server has never run before)

    latest_ver = Version.from_str(app.settings.VERSION)

    if latest_ver is None:
        raise RuntimeError(f"Invalid bancho.py version '{app.settings.VERSION}'")

    if latest_ver == current_ver:
        return  # already up to date

    # version changed; there may be sql changes.
    content = SQL_UPDATES_FILE.read_text()

    queries: list[str] = []
    q_lines: list[str] = []

    update_ver = None

    for line in content.splitlines():
        if not line:
            continue

        if line.startswith("#"):
            # may be normal comment or new version
            if r_match := VERSION_RGX.fullmatch(line):
                update_ver = Version.from_str(r_match["ver"])

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

    if queries:
        logging.info(f"Updating mysql structure (v{current_ver!r} -> v{latest_ver!r}).")

    # XXX: so it turns out we can't use a transaction here (at least with mysql)
    #      to roll back changes, as any structural changes to tables implicitly
    #      commit: https://dev.mysql.com/doc/refman/5.7/en/implicit-commit.html
    async with app.state.services.database.connection() as db_conn:
        for query in queries:
            try:
                await db_conn.execute(query)
            except pymysql.err.MySQLError as exc:
                logging.critical(f"Failed: {query}", exc_info=exc)
                logging.critical(
                    "SQL failed to update - unless you've been "
                    "modifying sql and know what caused this, "
                    "please please contact cmyui#0425.",
                )
                raise KeyboardInterrupt from exc
        else:
            # all queries executed successfully
            await db_conn.execute(
                "INSERT INTO startups (ver_major, ver_minor, ver_micro, datetime) "
                "VALUES (:major, :minor, :micro, NOW())",
                {
                    "major": latest_ver.major,
                    "minor": latest_ver.minor,
                    "micro": latest_ver.micro,
                },
            )


async def acquire_db_conn() -> AsyncIterator["databases.core.Connection"]:
    """Decorator to acquire a database connection for a handler."""
    async with database.connection() as conn:
        yield conn
