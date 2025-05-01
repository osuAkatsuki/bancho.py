from __future__ import annotations

import ipaddress
import logging
import pickle
import re
import secrets
from collections.abc import AsyncGenerator
from collections.abc import Mapping
from collections.abc import MutableMapping
from pathlib import Path
from typing import TypedDict

import datadog as datadog_module
import datadog.threadstats.base as datadog_client
import httpx
import pymysql
from redis import asyncio as aioredis

import app.settings
import app.state
from app._typing import IPAddress
from app.adapters.database import Database
from app.logging import Ansi
from app.logging import log

STRANGE_LOG_DIR = Path.cwd() / ".data/logs"

VERSION_RGX = re.compile(r"^# v(?P<ver>\d+\.\d+\.\d+)$")
SQL_UPDATES_FILE = Path.cwd() / "migrations/migrations.sql"


""" session objects """

http_client = httpx.AsyncClient()
database = Database(app.settings.DB_DSN)
redis: aioredis.Redis = aioredis.from_url(app.settings.REDIS_DSN)  # type: ignore[no-untyped-call]

datadog: datadog_client.ThreadStats | None = None
if str(app.settings.DATADOG_API_KEY) and str(app.settings.DATADOG_APP_KEY):
    datadog_module.initialize(
        api_key=str(app.settings.DATADOG_API_KEY),
        app_key=str(app.settings.DATADOG_APP_KEY),
    )
    datadog = datadog_client.ThreadStats()  # type: ignore[no-untyped-call]

ip_resolver: IPResolver

""" session usecases """


class Country(TypedDict):
    acronym: str
    numeric: int


class Geolocation(TypedDict):
    latitude: float
    longitude: float
    country: Country


# fmt: off
country_codes = {
    "oc": 1,   "eu": 2,   "ad": 3,   "ae": 4,   "af": 5,   "ag": 6,   "ai": 7,   "al": 8,
    "am": 9,   "an": 10,  "ao": 11,  "aq": 12,  "ar": 13,  "as": 14,  "at": 15,  "au": 16,
    "aw": 17,  "az": 18,  "ba": 19,  "bb": 20,  "bd": 21,  "be": 22,  "bf": 23,  "bg": 24,
    "bh": 25,  "bi": 26,  "bj": 27,  "bm": 28,  "bn": 29,  "bo": 30,  "br": 31,  "bs": 32,
    "bt": 33,  "bv": 34,  "bw": 35,  "by": 36,  "bz": 37,  "ca": 38,  "cc": 39,  "cd": 40,
    "cf": 41,  "cg": 42,  "ch": 43,  "ci": 44,  "ck": 45,  "cl": 46,  "cm": 47,  "cn": 48,
    "co": 49,  "cr": 50,  "cu": 51,  "cv": 52,  "cx": 53,  "cy": 54,  "cz": 55,  "de": 56,
    "dj": 57,  "dk": 58,  "dm": 59,  "do": 60,  "dz": 61,  "ec": 62,  "ee": 63,  "eg": 64,
    "eh": 65,  "er": 66,  "es": 67,  "et": 68,  "fi": 69,  "fj": 70,  "fk": 71,  "fm": 72,
    "fo": 73,  "fr": 74,  "fx": 75,  "ga": 76,  "gb": 77,  "gd": 78,  "ge": 79,  "gf": 80,
    "gh": 81,  "gi": 82,  "gl": 83,  "gm": 84,  "gn": 85,  "gp": 86,  "gq": 87,  "gr": 88,
    "gs": 89,  "gt": 90,  "gu": 91,  "gw": 92,  "gy": 93,  "hk": 94,  "hm": 95,  "hn": 96,
    "hr": 97,  "ht": 98,  "hu": 99,  "id": 100, "ie": 101, "il": 102, "in": 103, "io": 104,
    "iq": 105, "ir": 106, "is": 107, "it": 108, "jm": 109, "jo": 110, "jp": 111, "ke": 112,
    "kg": 113, "kh": 114, "ki": 115, "km": 116, "kn": 117, "kp": 118, "kr": 119, "kw": 120,
    "ky": 121, "kz": 122, "la": 123, "lb": 124, "lc": 125, "li": 126, "lk": 127, "lr": 128,
    "ls": 129, "lt": 130, "lu": 131, "lv": 132, "ly": 133, "ma": 134, "mc": 135, "md": 136,
    "mg": 137, "mh": 138, "mk": 139, "ml": 140, "mm": 141, "mn": 142, "mo": 143, "mp": 144,
    "mq": 145, "mr": 146, "ms": 147, "mt": 148, "mu": 149, "mv": 150, "mw": 151, "mx": 152,
    "my": 153, "mz": 154, "na": 155, "nc": 156, "ne": 157, "nf": 158, "ng": 159, "ni": 160,
    "nl": 161, "no": 162, "np": 163, "nr": 164, "nu": 165, "nz": 166, "om": 167, "pa": 168,
    "pe": 169, "pf": 170, "pg": 171, "ph": 172, "pk": 173, "pl": 174, "pm": 175, "pn": 176,
    "pr": 177, "ps": 178, "pt": 179, "pw": 180, "py": 181, "qa": 182, "re": 183, "ro": 184,
    "ru": 185, "rw": 186, "sa": 187, "sb": 188, "sc": 189, "sd": 190, "se": 191, "sg": 192,
    "sh": 193, "si": 194, "sj": 195, "sk": 196, "sl": 197, "sm": 198, "sn": 199, "so": 200,
    "sr": 201, "st": 202, "sv": 203, "sy": 204, "sz": 205, "tc": 206, "td": 207, "tf": 208,
    "tg": 209, "th": 210, "tj": 211, "tk": 212, "tm": 213, "tn": 214, "to": 215, "tl": 216,
    "tr": 217, "tt": 218, "tv": 219, "tw": 220, "tz": 221, "ua": 222, "ug": 223, "um": 224,
    "us": 225, "uy": 226, "uz": 227, "va": 228, "vc": 229, "ve": 230, "vg": 231, "vi": 232,
    "vn": 233, "vu": 234, "wf": 235, "ws": 236, "ye": 237, "yt": 238, "rs": 239, "za": 240,
    "zm": 241, "me": 242, "zw": 243, "xx": 244, "a2": 245, "o1": 246, "ax": 247, "gg": 248,
    "im": 249, "je": 250, "bl": 251, "mf": 252,
}
# fmt: on


class IPResolver:
    def __init__(self) -> None:
        self.cache: MutableMapping[str, IPAddress] = {}

    def get_ip(self, headers: Mapping[str, str]) -> IPAddress:
        """Resolve the IP address from the headers."""
        ip_str = headers.get("CF-Connecting-IP")
        if ip_str is None:
            forwards = headers["X-Forwarded-For"].split(",")

            if len(forwards) != 1:
                ip_str = forwards[0]
            else:
                ip_str = headers["X-Real-IP"]

        ip = self.cache.get(ip_str)
        if ip is None:
            ip = ipaddress.ip_address(ip_str)
            self.cache[ip_str] = ip

        return ip


async def fetch_geoloc(
    ip: IPAddress,
    headers: Mapping[str, str] | None = None,
) -> Geolocation | None:
    """Attempt to fetch geolocation data by any means necessary."""
    geoloc = None
    if headers is not None:
        geoloc = _fetch_geoloc_from_headers(headers)

    if geoloc is None:
        geoloc = await _fetch_geoloc_from_ip(ip)

    return geoloc


def _fetch_geoloc_from_headers(headers: Mapping[str, str]) -> Geolocation | None:
    """Attempt to fetch geolocation data from http headers."""
    geoloc = __fetch_geoloc_cloudflare(headers)

    if geoloc is None:
        geoloc = __fetch_geoloc_nginx(headers)

    return geoloc


def __fetch_geoloc_cloudflare(headers: Mapping[str, str]) -> Geolocation | None:
    """Attempt to fetch geolocation data from cloudflare headers."""
    if not all(
        key in headers for key in ("CF-IPCountry", "CF-IPLatitude", "CF-IPLongitude")
    ):
        return None

    country_code = headers["CF-IPCountry"].lower()
    latitude = float(headers["CF-IPLatitude"])
    longitude = float(headers["CF-IPLongitude"])

    return {
        "latitude": latitude,
        "longitude": longitude,
        "country": {
            "acronym": country_code,
            "numeric": country_codes[country_code],
        },
    }


def __fetch_geoloc_nginx(headers: Mapping[str, str]) -> Geolocation | None:
    """Attempt to fetch geolocation data from nginx headers."""
    if not all(
        key in headers for key in ("X-Country-Code", "X-Latitude", "X-Longitude")
    ):
        return None

    country_code = headers["X-Country-Code"].lower()
    latitude = float(headers["X-Latitude"])
    longitude = float(headers["X-Longitude"])

    return {
        "latitude": latitude,
        "longitude": longitude,
        "country": {
            "acronym": country_code,
            "numeric": country_codes[country_code],
        },
    }


async def _fetch_geoloc_from_ip(ip: IPAddress) -> Geolocation | None:
    """Fetch geolocation data based on ip (using ip-api)."""
    if not ip.is_private:
        url = f"http://ip-api.com/line/{ip}"
    else:
        url = "http://ip-api.com/line/"

    response = await http_client.get(
        url,
        params={
            "fields": ",".join(("status", "message", "countryCode", "lat", "lon")),
        },
    )
    if response.status_code != 200:
        log("Failed to get geoloc data: request failed.", Ansi.LRED)
        return None

    status, *lines = response.read().decode().split("\n")

    if status != "success":
        err_msg = lines[0]
        if err_msg == "invalid query":
            err_msg += f" ({url})"

        log(f"Failed to get geoloc data: {err_msg} for ip {ip}.", Ansi.LRED)
        return None

    country_acronym = lines[0].lower()

    return {
        "latitude": float(lines[1]),
        "longitude": float(lines[2]),
        "country": {
            "acronym": country_acronym,
            "numeric": country_codes[country_acronym],
        },
    }


async def log_strange_occurrence(obj: object) -> None:
    pickled_obj: bytes = pickle.dumps(obj)
    uploaded = False

    if app.settings.AUTOMATICALLY_REPORT_PROBLEMS:
        # automatically reporting problems to cmyui's server
        response = await http_client.post(
            url="https://log.cmyui.xyz/",
            headers={
                "Bancho-Version": app.settings.VERSION,
                "Bancho-Domain": app.settings.DOMAIN,
            },
            content=pickled_obj,
        )
        if response.status_code == 200 and response.read() == b"ok":
            uploaded = True
            log(
                "Logged strange occurrence to cmyui's server. "
                "Thank you for your participation! <3",
                Ansi.LBLUE,
            )
        else:
            log(
                f"Autoupload to cmyui's server failed (HTTP {response.status_code})",
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

        log(
            "Logged strange occurrence to" + "/".join(log_file.parts[-4:]),
            Ansi.LYELLOW,
        )
        log(
            "It would be greatly appreciated if you could forward this to the "
            "bancho.py development team. To do so, please email josh@akatsuki.gg",
            Ansi.LYELLOW,
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

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented

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
    def from_str(cls, s: str) -> Version | None:
        split = s.split(".")
        if len(split) == 3:
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
        response = await http_client.get(url)
        json = response.json()

        if response.status_code == 200 and json:
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
            log(
                f"{module} has an update available "
                f"[{current_ver!r} -> {latest_ver!r}]",
                Ansi.LMAGENTA,
            )

    if updates_available:
        log(
            "Python modules can be updated with "
            "`python3.11 -m pip install -U <modules>`.",
            Ansi.LMAGENTA,
        )


# sql migrations


async def _get_current_sql_structure_version() -> Version | None:
    """Get the last launched version of the server."""
    res = await app.state.services.database.fetch_one(
        "SELECT ver_major, ver_minor, ver_micro "
        "FROM startups ORDER BY datetime DESC LIMIT 1",
    )

    if res:
        return Version(res["ver_major"], res["ver_minor"], res["ver_micro"])

    return None


async def run_sql_migrations() -> None:
    """Update the sql structure, if it has changed."""
    software_version = Version.from_str(app.settings.VERSION)
    if software_version is None:
        raise RuntimeError(f"Invalid bancho.py version '{app.settings.VERSION}'")

    last_run_migration_version = await _get_current_sql_structure_version()
    if not last_run_migration_version:
        # Migrations have never run before - this is the first time starting the server.
        # We'll insert the current version into the database, so future versions know to migrate.
        await app.state.services.database.execute(
            "INSERT INTO startups (ver_major, ver_minor, ver_micro, datetime) "
            "VALUES (:major, :minor, :micro, NOW())",
            {
                "major": software_version.major,
                "minor": software_version.minor,
                "micro": software_version.micro,
            },
        )
        return  # already up to date (server has never run before)

    if software_version == last_run_migration_version:
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
            r_match = VERSION_RGX.fullmatch(line)
            if r_match:
                update_ver = Version.from_str(r_match["ver"])

            continue
        elif not update_ver:
            continue

        # we only need the updates between the
        # previous and new version of the server.
        if last_run_migration_version < update_ver <= software_version:
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
        log(
            f"Updating mysql structure (v{last_run_migration_version!r} -> v{software_version!r}).",
            Ansi.LMAGENTA,
        )

    # XXX: we can't use a transaction here with mysql as structural changes to
    # tables implicitly commit: https://dev.mysql.com/doc/refman/5.7/en/implicit-commit.html
    for query in queries:
        try:
            await app.state.services.database.execute(query)
        except pymysql.err.MySQLError as exc:
            log(f"Failed: {query}", Ansi.GRAY)
            log(repr(exc))
            log(
                "SQL failed to update - unless you've been "
                "modifying sql and know what caused this, "
                "please contact @cmyui on Discord.",
                Ansi.LRED,
            )
            raise KeyboardInterrupt from exc
    else:
        # all queries executed successfully
        await app.state.services.database.execute(
            "INSERT INTO startups (ver_major, ver_minor, ver_micro, datetime) "
            "VALUES (:major, :minor, :micro, NOW())",
            {
                "major": software_version.major,
                "minor": software_version.minor,
                "micro": software_version.micro,
            },
        )
