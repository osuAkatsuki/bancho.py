from __future__ import annotations

import ipaddress
import pickle
import re
import secrets
from collections.abc import Mapping
from collections.abc import MutableMapping
from pathlib import Path
from typing import TypedDict

import datadog as datadog_module
import datadog.threadstats.base as datadog_client
import httpx
from redis import asyncio as aioredis

import app.adapters.database
import app.settings
import app.state
from app._typing import IPAddress
from app.adapters.database import Database
from app.logging import Ansi
from app.logging import log

STRANGE_LOG_DIR = Path.cwd() / ".data/logs"


""" session objects """

http_client = httpx.AsyncClient()
database = Database(
    url=app.adapters.database.make_dsn(
        dialect="mysql",
        user=app.settings.DB_USER,
        host=app.settings.DB_HOST,
        port=app.settings.DB_PORT,
        database=app.settings.DB_NAME,
        driver="aiomysql",
        password=app.settings.DB_PASS,
    ),
)
redis: aioredis.Redis = aioredis.from_url(app.settings.REDIS_DSN)

datadog: datadog_client.ThreadStats | None = None
if str(app.settings.DATADOG_API_KEY) and str(app.settings.DATADOG_APP_KEY):
    datadog_module.initialize(
        api_key=str(app.settings.DATADOG_API_KEY),
        app_key=str(app.settings.DATADOG_APP_KEY),
    )
    datadog = datadog_client.ThreadStats()

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
