from starlette.config import Config

config = Config(".env")

DB_DSN: str = config("DB_DSN")
OSU_API_KEY: str = config("OSU_API_KEY")

DOMAIN: str = config("DOMAIN", default="cmyui.xyz")
MIRROR_URL: str = config("MIRROR_URL", default="https://api.chimu.moe/v1")

COMMAND_PREFIX: str = config("COMMAND_PREFIX", default="!")
MAIN_MENU_ICON: str = config(
    "MAIN_MENU_ICON",
    default="https://akatsuki.pw/static/logos/logo_ingame.png|https://akatsuki.pw",
)

DATADOG_API_KEY: str = config("DATADOG_API_KEY")
DATADOG_APP_KEY: str = config("DATADOG_APP_KEY")

DEBUG: bool = config("DEBUG", cast=bool, default=False)

AUTOMATICALLY_REPORT_PROBLEMS: bool = config(
    "AUTOMATICALLY_REPORT_PROBLEMS",
    cast=bool,
    default=True,
)

# WARN: this enables potentially dangerous settings,
# including an in-game command which gives users with
# the Privileges.DANGEROUS bit to use the access the
# python interpreter directly. USE AT YOUR OWN RISK.
DEVELOPER_MODE: bool = config("DEVELOPER_MODE", cast=bool, default=False)

# don't touch this :)
VERSION = "4.0.0"
