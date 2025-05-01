# #!/usr/bin/env python3.11
from __future__ import annotations

import asyncio
import io
import pprint
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import starlette.routing
from fastapi import FastAPI
from fastapi import status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.requests import Request
from fastapi.responses import ORJSONResponse
from fastapi.responses import Response
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import ClientDisconnect

import app.bg_loops
import app.settings
import app.state
import app.utils
from app.api import api_router  # type: ignore[attr-defined]
from app.api import domains
from app.api import middlewares
from app.logging import Ansi
from app.logging import log
from app.objects import collections


class BanchoAPI(FastAPI):
    def openapi(self) -> dict[str, Any]:
        if not self.openapi_schema:
            routes = self.routes
            starlette_hosts = [
                host
                for host in super().routes
                if isinstance(host, starlette.routing.Host)
            ]

            # XXX:HACK fastapi will not show documentation for routes
            # added through use sub applications using the Host class
            # (e.g. app.host('other.domain', app2))
            for host in starlette_hosts:
                for route in host.routes:
                    if route not in routes:
                        routes.append(route)

            self.openapi_schema = get_openapi(
                title=self.title,
                version=self.version,
                openapi_version=self.openapi_version,
                description=self.description,
                terms_of_service=self.terms_of_service,
                contact=self.contact,
                license_info=self.license_info,
                routes=routes,
                tags=self.openapi_tags,
                servers=self.servers,
            )

        return self.openapi_schema


@asynccontextmanager
async def lifespan(asgi_app: BanchoAPI) -> AsyncIterator[None]:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")

    app.utils.ensure_persistent_volumes_are_available()

    app.state.loop = asyncio.get_running_loop()

    if app.utils.is_running_as_admin():
        log(
            "Running the server with root privileges is not recommended.",
            Ansi.LYELLOW,
        )

    await app.state.services.database.connect()
    await app.state.services.redis.initialize()  # type: ignore[unused-awaitable]

    if app.state.services.datadog is not None:
        app.state.services.datadog.start(  # type: ignore[no-untyped-call]
            flush_in_thread=True,
            flush_interval=15,
        )
        app.state.services.datadog.gauge("bancho.online_players", 0)  # type: ignore[no-untyped-call]

    app.state.services.ip_resolver = app.state.services.IPResolver()

    await app.state.services.run_sql_migrations()

    await collections.initialize_ram_caches()

    await app.bg_loops.initialize_housekeeping_tasks()

    log("Startup process complete.", Ansi.LGREEN)
    log(
        f"Listening @ {app.settings.APP_HOST}:{app.settings.APP_PORT}",
        Ansi.LMAGENTA,
    )

    yield

    # we want to attempt to gracefully finish any ongoing connections
    # and shut down any of the housekeeping tasks running in the background.
    await app.state.sessions.cancel_housekeeping_tasks()

    # shutdown services

    await app.state.services.http_client.aclose()
    await app.state.services.database.disconnect()
    await app.state.services.redis.aclose()

    if app.state.services.datadog is not None:
        app.state.services.datadog.stop()  # type: ignore[no-untyped-call]
        app.state.services.datadog.flush()  # type: ignore[no-untyped-call]


def init_exception_handlers(asgi_app: BanchoAPI) -> None:
    @asgi_app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> Response:
        """Wrapper around 422 validation errors to print out info for devs."""
        log(f"Validation error on {request.url}", Ansi.LRED)
        pprint.pprint(exc.errors())

        return ORJSONResponse(
            content={"detail": jsonable_encoder(exc.errors())},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


def init_middlewares(asgi_app: BanchoAPI) -> None:
    """Initialize our app's middleware stack."""
    asgi_app.add_middleware(middlewares.MetricsMiddleware)

    @asgi_app.middleware("http")
    async def http_middleware(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        # if an osu! client is waiting on leaderboard data
        # and switches to another leaderboard, it will cancel
        # the previous request midway, resulting in a large
        # error in the console. this is to catch that :)

        try:
            return await call_next(request)
        except ClientDisconnect:
            # client disconnected from the server
            # while we were reading the body.
            return Response("Client is stupppod")
        except RuntimeError as exc:
            if exc.args[0] == "No response returned.":
                # client disconnected from the server
                # while we were sending the response.
                return Response("Client is stupppod")

            # unrelated issue, raise normally
            raise exc


def init_routes(asgi_app: BanchoAPI) -> None:
    """Initialize our app's route endpoints."""
    for domain in ("ppy.sh", app.settings.DOMAIN):
        for subdomain in ("c", "ce", "c4", "c5", "c6"):
            asgi_app.host(f"{subdomain}.{domain}", domains.cho.router)

        asgi_app.host(f"osu.{domain}", domains.osu.router)
        asgi_app.host(f"b.{domain}", domains.map.router)

        # bancho.py's developer-facing api
        asgi_app.host(f"api.{domain}", api_router)


def init_api() -> BanchoAPI:
    """Create & initialize our app."""
    asgi_app = BanchoAPI(lifespan=lifespan)

    init_middlewares(asgi_app)
    init_exception_handlers(asgi_app)
    init_routes(asgi_app)

    return asgi_app


asgi_app = init_api()
