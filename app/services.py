import asyncio
import importlib.metadata
import ipaddress
import pickle
import secrets
from pathlib import Path
from typing import AsyncGenerator
from typing import Optional
from typing import TypedDict

import aiohttp
import aioredis
import cmyui
import databases
import datadog as datadog_module
import datadog.threadstats.base as datadog_client
import geoip2.database
from cmyui.logging import Ansi
from cmyui.logging import log
from cmyui.logging import printc
from cmyui.logging import Rainbow

from app import settings
from app.constants.countries import country_codes

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address

STRANGE_LOG_DIR = Path.cwd() / ".data/logs"
GEOLOC_DB_FILE = Path.cwd() / "ext/GeoLite2-City.mmdb"


""" session objects """

http: "aiohttp.ClientSession"
database: "databases.Database"
redis: "aioredis.Redis"
geoloc_db: "geoip2.database.Reader"
datadog: Optional[datadog_client.ThreadStats]

housekeeping_tasks: list[asyncio.Task] = []

""" session usecases """


class Country(TypedDict):
    acronym: str
    numeric: int


class Geolocation(TypedDict):
    latitude: float
    longitude: float
    country: Country


def fetch_geoloc_db(ip: IPAddress) -> Optional[Geolocation]:
    """Fetch geolocation data based on ip (using local db)."""
    res = geoloc_db.city(ip)

    if res.country.iso_code is not None:
        acronym = res.country.iso_code.lower()
    else:
        acronym = "XX"

    return {
        "latitude": res.location.latitude or 0.0,
        "longitude": res.location.longitude or 0.0,
        "country": {
            "acronym": acronym,
            "numeric": country_codes[acronym],
        },
    }


async def fetch_geoloc_web(ip: IPAddress) -> Optional[Geolocation]:
    """Fetch geolocation data based on ip (using ip-api)."""
    url = f"http://ip-api.com/line/{ip}"

    async with http.get(url) as resp:
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
        "country": {
            "acronym": acronym,
            "numeric": country_codes[acronym],
        },
    }


async def log_strange_occurrence(obj: object) -> None:
    pickled_obj: bytes = pickle.dumps(obj)
    uploaded = False

    if settings.AUTOMATICALLY_REPORT_PROBLEMS:
        # automatically reporting problems to cmyui's server
        async with http.post(
            url="https://log.cmyui.xyz/",
            headers={
                "Gulag-Version": settings.VERSION,
                "Gulag-Domain": settings.DOMAIN,
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


# dependency management


async def _get_latest_dependency_versions() -> AsyncGenerator[
    tuple[str, cmyui.Version, cmyui.Version],
    None,
]:
    """Return the current installed & latest version for each dependency."""
    with open("requirements.txt") as f:
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
        async with http.get(url) as resp:
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
            "`python3.10 -m pip install -U <modules>`.",
            Ansi.LMAGENTA,
        )
