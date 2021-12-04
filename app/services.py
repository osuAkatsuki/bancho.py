import ipaddress
from pathlib import Path
from typing import Optional
from typing import TypedDict

import aiohttp
import geoip2.database
from cmyui.logging import Ansi
from cmyui.logging import log
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker

import app.misc.utils
import app.settings
from app.constants.countries import country_codes

GEOLOC_DB_FILE = Path.cwd() / "ext/GeoLite2-City.mmdb"

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


# create our sessions
database = create_async_engine(app.settings.DB_DSN, future=True)
database_session = sessionmaker(database, expire_on_commit=False, class_=AsyncSession)
geoloc_db = geoip2.database.Reader(GEOLOC_DB_FILE)
# TODO: redis
http_session = aiohttp.ClientSession(
    json_serialize=app.misc.utils.orjson_serialize_to_str,
)


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
        "country": {"acronym": acronym, "numeric": country_codes[acronym]},
    }


async def fetch_geoloc_web(ip: IPAddress) -> Optional[Geolocation]:
    """Fetch geolocation data based on ip (using ip-api)."""
    url = f"http://ip-api.com/line/{ip}"

    async with http_session.get(url) as resp:
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


# dependency management
from typing import AsyncGenerator

import cmyui
from cmyui.logging import Ansi
from cmyui.logging import log
from app import services
import importlib.metadata


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
        async with services.http_session.get(url) as resp:
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
