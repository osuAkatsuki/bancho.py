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
import asyncio
import os

from cmyui.logging import Ansi
from cmyui.logging import log
from fastapi import FastAPI
from fastapi.requests import Request

from . import domains
from mount.app import bg_loops
from mount.app import services
from mount.app import settings
from mount.app.api import middlewares
from mount.app.objects import collections


# TODO:
# - dependency management
# - database migrations
# - safety checks
# - install debugging hooks
# - static api keys
# - datadog metrics


def init_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def handle_base_exception(request: Request, exc: Exception):
        pass


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

        # start services
        await services.database.connect()

        # start housekeeping tasks
        # services.housekeeping_tasks.extend(
        await bg_loops.initialize_housekeeping_tasks()

        from mount.app import db_models

        row = await services.database.fetch_one(
            db_models.maps.select().where(
                db_models.maps.c.id == 924414,
            ),
        )
        # populate ram caches
        await collections.populate_sessions()

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        # stop services
        await services.database.disconnect()
        await services.http.close()
        services.geoloc_db.close()

        if services.datadog is not None:
            services.datadog.stop()
            services.datadog.flush()

        # stop housekeeping tasks
        await bg_loops.cancel_tasks(services.housekeeping_tasks)


def init_routes(app: FastAPI) -> None:
    """Initialize our app's route endpoints."""
    # endpoints for the osu! client
    for domain in ("ppy.sh", settings.DOMAIN):
        app.host(f"a.{domain}", domains.ava.router)

        for subdomain in ("c", "ce", "c4", "c5", "c6"):
            app.host(f"{subdomain}.{domain}", domains.cho.router)

        app.host(f"osu.{domain}", domains.osu.router)
        app.host(f"b.{domain}", domains.map.router)

        # gulag's developer-facing api
        app.host(f"api.{domain}", domains.api.router)


def init_api() -> FastAPI:
    """Create & initialize our app."""
    app = FastAPI()

    init_exception_handlers(app)
    init_middlewares(app)
    init_events(app)
    init_routes(app)

    return app


app = init_api()
