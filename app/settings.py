from starlette.config import Config

config = Config(".env")

DB_DSN: str = config("DB_DSN")
OSU_API_KEY: str = config("OSU_API_KEY")

DOMAIN: str = config("DOMAIN", default="cmyui.xyz")
MIRROR_URL: str = config("MIRROR_URL", default="https://api.chimu.moe/v1")

COMMAND_PREFIX: str = config("COMMAND_PREFIX", default="!")
DEBUG: bool = config("DEBUG", cast=bool, default=False)

# WARN: this enables potentially dangerous settings,
# including an in-game command which gives users with
# the Privileges.DANGEROUS bit to use the access the
# python interpreter directly. USE AT YOUR OWN RISK.
DEVELOPER_MODE: bool = config("DEVELOPER_MODE", cast=bool, default=False)
