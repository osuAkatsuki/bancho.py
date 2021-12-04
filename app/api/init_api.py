# #!/usr/bin/env python3.10
"""
gulag - the most developed, production-ready osu! server implementation

if you're interested in development, my test server is usually
up at https://c.cmyui.xyz. just use the same `-devserver cmyui.xyz`
connection method you would with any other modern server and you
should have no problems connecting. registration is done in-game
with osu!'s built-in registration (if you're worried about not being
properly connected while registering, the server should send back
https://i.cmyui.xyz/8-Vzy9NllPBp5K7L.png if you use a random login).

you can also test gulag's rest api using my test server,
e.g https://osu.cmyui.xyz/api/get_player_scores?id=3&scope=best
"""
import os
from pathlib import Path

import cmyui
from cmyui.logging import Ansi
from cmyui.logging import log
from fastapi import FastAPI

from .domains import ava
from .domains import cho
from .domains import osu
from app import services
from app import settings
from app.objects import glob

# from .domains import map

GEOLOC_DB_FILE = Path.cwd() / "ext/GeoLite2-City.mmdb"

# # !! review code that uses this before modifying it.
glob.version = cmyui.Version(3, 6, 1)


# TODO:
# - redis
# - http session
# - datadog
# - maxmind db
# - dependency management
# - database migrations
# - housekeeping tasks
# - initialize ram caches
# - safety checks
# - offline mode
# - install debugging hooks
# - uvloop


def init_events(app: FastAPI) -> None:
    """Initialize our app's event handlers."""

    @app.on_event("startup")
    async def on_startup() -> None:
        if os.geteuid() == 0:
            log(
                "Running the server with root privileges is not recommended.",
                Ansi.LRED,
            )

        await services.database.connect()

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        await services.database.disconnect()


def init_routes(app: FastAPI) -> None:
    """Initialize our app's route endpoints."""
    for domain in ("ppy.sh", settings.DOMAIN):
        app.host(f"a.{domain}", ava.router)
        app.host(f"osu.{domain}", osu.router)

        for subdomain in ("c", "ce", "c4", "c5", "c6"):
            app.host(f"{subdomain}.{domain}", cho.router)


def init_api() -> FastAPI:
    """Create & initialize our app."""
    app = FastAPI()

    init_events(app)
    init_routes(app)

    return app


app = init_api()
