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
from fastapi import Response
from fastapi.exceptions import RequestValidationError

import app.settings
import app.state
import app.utils
import bg_loops
from app.api import domains
from app.api import middlewares
from app.objects import collections


def init_exception_handlers(asgi_app: FastAPI) -> None:
    @asgi_app.middleware("http")
    async def wtf(request, call_next):
        try:
            return await call_next(request)
        except RuntimeError as exc:
            # NOTE: TODO note
            if exc.args[0] == "No response returned.":
                return Response("Client is stupppod")

            raise

    @asgi_app.exception_handler(RequestValidationError)
    async def x(r, e):
        print()


def init_middlewares(asgi_app: FastAPI) -> None:
    """Initialize our app's middleware stack."""
    asgi_app.add_middleware(middlewares.MetricsMiddleware)


def init_events(asgi_app: FastAPI) -> None:
    """Initialize our app's event handlers."""

    @asgi_app.on_event("startup")
    async def on_startup() -> None:
        app.state.loop = asyncio.get_running_loop()

        if os.geteuid() == 0:
            log(
                "Running the server with root privileges is not recommended.",
                Ansi.LRED,
            )

        await app.state.services.database.connect()
        await app.state.services.redis.initialize()

        if app.state.services.datadog is not None:
            app.state.services.datadog.start(flush_in_thread=True, flush_interval=15)
            app.state.services.datadog.gauge("gulag.online_players", 0)

        async with app.state.services.database.connection() as db_conn:
            await collections.initialize_ram_caches(db_conn)

        await bg_loops.initialize_housekeeping_tasks()

    @asgi_app.on_event("shutdown")
    async def on_shutdown() -> None:
        # we want to attempt to gracefully finish any ongoing connections
        # and shut down any of the housekeeping tasks running in the background.
        await app.state.sessions.cancel_housekeeping_tasks()

        # shutdown services

        await app.state.services.http.close()
        await app.state.services.database.disconnect()
        await app.state.services.redis.close()
        await app.state.services.http.close()

        if app.state.services.geoloc_db is not None:
            app.state.services.geoloc_db.close()


def init_routes(asgi_app: FastAPI) -> None:
    """Initialize our app's route endpoints."""
    for domain in ("ppy.sh", app.settings.DOMAIN):
        asgi_app.host(f"a.{domain}", domains.ava.router)

        for subdomain in ("c", "ce", "c4", "c5", "c6"):
            asgi_app.host(f"{subdomain}.{domain}", domains.cho.router)

        asgi_app.host(f"osu.{domain}", domains.osu.router)
        asgi_app.host(f"b.{domain}", domains.map.router)

        # gulag's developer-facing api
        asgi_app.host(f"api.{domain}", domains.api.router)


def init_api() -> FastAPI:
    """Create & initialize our app."""
    asgi_app = FastAPI()

    init_middlewares(asgi_app)
    init_exception_handlers(asgi_app)
    init_events(asgi_app)
    init_routes(asgi_app)

    return asgi_app


asgi_app = init_api()
