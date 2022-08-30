from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def read_bool(value: str) -> bool:
    return value.lower() in ("true", "1", "yes")


def read_list(value: str) -> list[str]:
    return value.split(",") if value else []


SERVER_ADDR = os.environ["SERVER_ADDR"]
SERVER_PORT = int(v) if (v := os.getenv("SERVER_PORT", None)) else None

DB_HOST = os.environ["DB_HOST"]
DB_PORT = int(os.environ["DB_PORT"])
DB_USER = os.environ["DB_USER"]
DB_PASS = os.environ["DB_PASS"]
DB_NAME = os.environ["DB_NAME"]
DB_DSN = f"mysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

REDIS_HOST = os.environ["REDIS_HOST"]
REDIS_PORT = int(os.environ["REDIS_PORT"])
REDIS_USER = os.environ["REDIS_USER"]
REDIS_PASS = os.environ["REDIS_PASS"]
REDIS_DB = int(os.environ["REDIS_DB"])
REDIS_DSN = f"redis://{REDIS_USER}:{REDIS_PASS}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

OSU_API_KEY = os.environ["OSU_API_KEY"]

DOMAIN = os.environ["DOMAIN"]
MIRROR_URL = os.environ["MIRROR_URL"]

COMMAND_PREFIX = os.environ["COMMAND_PREFIX"]

SEASONAL_BGS = read_list(os.environ["SEASONAL_BGS"])

MENU_ICON_URL = os.environ["MENU_ICON_URL"]
MENU_ONCLICK_URL = os.environ["MENU_ONCLICK_URL"]

DATADOG_API_KEY = os.environ["DATADOG_API_KEY"]
DATADOG_APP_KEY = os.environ["DATADOG_APP_KEY"]

DEBUG = read_bool(os.environ["DEBUG"])
REDIRECT_OSU_URLS = read_bool(os.environ["REDIRECT_OSU_URLS"])

PP_CACHED_ACCURACIES = [int(acc) for acc in read_list(os.environ["PP_CACHED_ACCS"])]
PP_CACHED_SCORES = [int(pp) for pp in read_list(os.environ["PP_CACHED_SCORES"])]

DISALLOWED_NAMES = read_list(os.environ["DISALLOWED_NAMES"])
DISALLOWED_PASSWORDS = read_list(os.environ["DISALLOWED_PASSWORDS"])
DISALLOW_OLD_CLIENTS = read_bool(os.environ["DISALLOW_OLD_CLIENTS"])

DISCORD_AUDIT_LOG_WEBHOOK = os.environ["DISCORD_AUDIT_LOG_WEBHOOK"]

AUTOMATICALLY_REPORT_PROBLEMS = read_bool(os.environ["AUTOMATICALLY_REPORT_PROBLEMS"])

# advanced dev settings

## WARNING touch this once you've
##          read through what it enables.
##          you could put your server at risk.
DEVELOPER_MODE = read_bool(os.environ["DEVELOPER_MODE"])

## WARNING touch this if you know how
##          the migrations system works.
##          you'll regret it.
VERSION = "4.6.4"
