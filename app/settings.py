from __future__ import annotations

from typing import Optional

from databases import DatabaseURL
from starlette.config import Config
from starlette.datastructures import CommaSeparatedStrings
from starlette.datastructures import Secret

config = Config(".env")

SERVER_ADDR: str = config("SERVER_ADDR")
SERVER_PORT: Optional[int] = (
    int(v) if (v := config("SERVER_PORT", default=None)) else None
)

DB_DSN: DatabaseURL = config("DB_DSN", cast=DatabaseURL)
REDIS_DSN: str = config("REDIS_DSN")

OSU_API_KEY: Secret = config("OSU_API_KEY", cast=Secret)

DOMAIN: str = config("DOMAIN", default="cmyui.xyz")
MIRROR_URL: str = config("MIRROR_URL", default="https://api.chimu.moe/v1")

COMMAND_PREFIX: str = config("COMMAND_PREFIX", default="!")

SEASONAL_BGS: CommaSeparatedStrings = config(
    "SEASONAL_BGS",
    cast=CommaSeparatedStrings,
    default=CommaSeparatedStrings(
        [
            "https://akatsuki.pw/static/flower.png",
            "https://i.cmyui.xyz/nrMT4V2RR3PR.jpeg",
        ],
    ),
)

MENU_ICON_URL: str = config(
    "MENU_ICON_URL",
    default="https://akatsuki.pw/static/logos/logo_ingame.png",
)
MENU_ONCLICK_URL: str = config("MENU_ONCLICK_URL", default="https://akatsuki.pw")

DATADOG_API_KEY: Secret = config("DATADOG_API_KEY", cast=Secret)
DATADOG_APP_KEY: Secret = config("DATADOG_APP_KEY", cast=Secret)

DEBUG: bool = config("DEBUG", cast=bool, default=False)
REDIRECT_OSU_URLS: bool = config("REDIRECT_OSU_URLS", cast=bool, default=True)

PP_CACHED_ACCURACIES: list[int] = [
    int(acc)
    for acc in config(
        "PP_CACHED_ACCS",
        cast=CommaSeparatedStrings,
    )
]
PP_CACHED_SCORES: list[int] = [
    int(score)
    for score in config(
        "PP_CACHED_SCORES",
        cast=CommaSeparatedStrings,
    )
]

DISALLOWED_NAMES: CommaSeparatedStrings = config(
    "DISALLOWED_NAMES",
    cast=CommaSeparatedStrings,
)
DISALLOWED_PASSWORDS: CommaSeparatedStrings = config(
    "DISALLOWED_PASSWORDS",
    cast=CommaSeparatedStrings,
)

DISCORD_AUDIT_LOG_WEBHOOK: str = config("DISCORD_AUDIT_LOG_WEBHOOK")

# advanced dev settings

## WARNING: only touch this once you've
##          read through what it enables.
##          you could put your server at risk.
DEVELOPER_MODE: bool = config("DEVELOPER_MODE", cast=bool, default=False)

## WARNING: only touch this if you know how
##          the migrations system works.
##          you'll regret it.
VERSION = "4.3.2"
