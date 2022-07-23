from __future__ import annotations

from databases import DatabaseURL
from starlette.config import Config
from starlette.datastructures import CommaSeparatedStrings
from starlette.datastructures import Secret

config = Config(".env")

SERVER_ADDR = config("SERVER_ADDR")
SERVER_PORT = int(v) if (v := config("SERVER_PORT", default=None)) else None

DB_DSN = config("DB_DSN", cast=DatabaseURL)
REDIS_DSN = config("REDIS_DSN")

OSU_API_KEY = config("OSU_API_KEY", cast=Secret)

DOMAIN = config("DOMAIN")
MIRROR_URL = config("MIRROR_URL")

COMMAND_PREFIX = config("COMMAND_PREFIX")

SEASONAL_BGS = config("SEASONAL_BGS", cast=CommaSeparatedStrings)

MENU_ICON_URL = config("MENU_ICON_URL")
MENU_ONCLICK_URL = config("MENU_ONCLICK_URL")

DATADOG_API_KEY = config("DATADOG_API_KEY", cast=Secret)
DATADOG_APP_KEY = config("DATADOG_APP_KEY", cast=Secret)

DEBUG = config("DEBUG", cast=bool)
REDIRECT_OSU_URLS = config("REDIRECT_OSU_URLS", cast=bool)

PP_CACHED_ACCURACIES = [
    int(acc) for acc in config("PP_CACHED_ACCS", cast=CommaSeparatedStrings)
]
PP_CACHED_SCORES = [
    int(score) for score in config("PP_CACHED_SCORES", cast=CommaSeparatedStrings)
]

DISALLOWED_NAMES = config("DISALLOWED_NAMES", cast=CommaSeparatedStrings)
DISALLOWED_PASSWORDS = config("DISALLOWED_PASSWORDS", cast=CommaSeparatedStrings)

DISCORD_AUDIT_LOG_WEBHOOK = config("DISCORD_AUDIT_LOG_WEBHOOK")

AUTOMATICALLY_REPORT_PROBLEMS = config("AUTOMATICALLY_REPORT_PROBLEMS", cast=bool)

# advanced dev settings

## WARNING touch this once you've
##          read through what it enables.
##          you could put your server at risk.
DEVELOPER_MODE = config("DEVELOPER_MODE", cast=bool)

## WARNING touch this if you know how
##          the migrations system works.
##          you'll regret it.
VERSION = "4.4.2"
