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

from cmyui.logging import Ansi
from cmyui.logging import log
from fastapi import FastAPI

from . import domains
from mount.app import services
from mount.app import settings
from mount.app.api import middlewares


# TODO:
# - housekeeping tasks
# - initialize ram caches
# - dependency management
# - database migrations
# - safety checks
# - install debugging hooks
# - static api keys
# - datadog metrics


def init_middlewares(app: FastAPI) -> None:
    """Initialize our app's middleware stack."""
    app.add_middleware(middlewares.MetricsMiddleware)


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
        await services.http.close()
        services.geoloc_db.close()

        if services.datadog is not None:
            services.datadog.stop()
            services.datadog.flush()


def init_routes(app: FastAPI) -> None:
    """Initialize our app's route endpoints."""
    # endpoints for the osu! client
    app.include_router(domains.ava.router)
    app.include_router(domains.osu.router)
    app.include_router(domains.cho.router)
    app.include_router(domains.map.router)

    # gulag's developer-facing api
    app.include_router(domains.api.router)


def init_api() -> FastAPI:
    """Create & initialize our app."""
    app = FastAPI()

    init_middlewares(app)
    init_events(app)
    init_routes(app)

    return app


app = init_api()
