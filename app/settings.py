from __future__ import annotations

from typing import cast
from typing import TYPE_CHECKING

from databases import DatabaseURL
from starlette.config import Config
from starlette.datastructures import CommaSeparatedStrings
from starlette.datastructures import Secret

if TYPE_CHECKING:
    from typing import Optional

    from app._typing import AppEnvironments

config = Config(".env")

# configuration options

APP_ENV = cast("AppEnvironments", config("APP_ENV"))

SERVER_ADDR: str = config("SERVER_ADDR")
SERVER_PORT: Optional[int] = (
    int(v) if (v := config("SERVER_PORT", default=None)) else None
)

DB_HOST = config("DB_HOST")
DB_PORT = config("DB_PORT", cast=int)
DB_USER = config("DB_USER")
DB_PASS = config("DB_PASS")
DB_NAME = config("DB_NAME")

DB_DSN = DatabaseURL(
    f"mysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
)
TEST_DB_DSN = DatabaseURL(
    f"mysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}_test",
)

REDIS_HOST = config("REDIS_HOST")
REDIS_PORT = config("REDIS_PORT", cast=int)
# TODO: support for redis auth?

REDIS_DSN = f"redis://{REDIS_HOST}:{REDIS_PORT}"
# TODO: TEST_REDIS_DSN?

OSU_API_KEY = config("OSU_API_KEY", cast=Secret)

DOMAIN = config("DOMAIN")
MIRROR_URL = config("MIRROR_URL")

COMMAND_PREFIX = config("COMMAND_PREFIX")
SEASONAL_BGS = config("SEASONAL_BGS", cast=CommaSeparatedStrings)

MENU_ICON_URL = config("MENU_ICON_URL")
MENU_ONCLICK_URL = config("MENU_ONCLICK_URL")

DATADOG_API_KEY = config("DATADOG_API_KEY", cast=Secret)
DATADOG_APP_KEY = config("DATADOG_APP_KEY", cast=Secret)

# CRITICAL: 50 | ERROR: 40 | WARNING: 30 | INFO: 20 | DEBUG: 10
LOG_LEVEL = config("LOG_LEVEL", cast=int)

REDIRECT_OSU_URLS = config("REDIRECT_OSU_URLS", cast=bool)

PP_CACHED_ACCURACIES = [
    int(acc) for acc in config("PP_CACHED_ACCS", cast=CommaSeparatedStrings)
]
PP_CACHED_SCORES = [
    int(score) for score in config("PP_CACHED_SCORES", cast=CommaSeparatedStrings)
]

DISALLOWED_NAMES = config("DISALLOWED_NAMES", cast=CommaSeparatedStrings)

DISCORD_AUDIT_LOG_WEBHOOK = config("DISCORD_AUDIT_LOG_WEBHOOK")

AUTOMATICALLY_REPORT_PROBLEMS = config("AUTOMATICALLY_REPORT_PROBLEMS", cast=bool)

# advanced dev settings

## WARNING: only touch this once you've
##          read through what it enables.
##          you could put your server at risk.
DEVELOPER_MODE = config("DEVELOPER_MODE", cast=bool)

## WARNING: only touch this if you know how
##          the migrations system works.
##          you'll regret it.
VERSION = "5.0.0"
