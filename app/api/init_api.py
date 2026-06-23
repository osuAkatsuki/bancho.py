# #!/usr/bin/env python3.11
from __future__ import annotations

import asyncio
import io
import pprint
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from typing import cast

import starlette.routing
from fastapi import APIRouter
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
from starlette.types import ExceptionHandler
from typing_extensions import override

import app.bg_loops
import app.settings
import app.state
import app.utils
from app.api import middlewares
from app.api.domains import cho as cho_domain
from app.api.domains import map as map_domain
from app.api.domains import osu as osu_domain
from app.api.v1 import apiv1_router
from app.api.v2 import apiv2_router
from app.logging import Ansi
from app.logging import log
from app.objects import collections

api_router = APIRouter()
api_router.include_router(apiv1_router)
api_router.include_router(apiv2_router)


class BanchoAPI(FastAPI):
    @override
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
    stdout = sys.stdout
    if isinstance(stdout, io.TextIOWrapper):
        stdout.reconfigure(encoding="utf-8")

    app.utils.ensure_persistent_volumes_are_available()

    app.state.loop = asyncio.get_running_loop()

    if app.utils.is_running_as_admin():
        log(
            "Running the server with root privileges is not recommended.",
            Ansi.LYELLOW,
        )

    await app.state.services.database.connect()
    app.state.services.redis = await app.state.services.redis.initialize()

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
        cast(Any, app.state.services.datadog).stop()
        app.state.services.datadog.flush()  # type: ignore[no-untyped-call]


def init_exception_handlers(asgi_app: BanchoAPI) -> None:
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

    asgi_app.add_exception_handler(
        RequestValidationError,
        cast(ExceptionHandler, handle_validation_error),
    )


def init_middlewares(asgi_app: BanchoAPI) -> None:
    """Initialize our app's middleware stack."""
    asgi_app.add_middleware(middlewares.MetricsMiddleware)

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

    asgi_app.middleware("http")(http_middleware)


def init_routes(asgi_app: BanchoAPI) -> None:
    """Initialize our app's route endpoints."""
    for domain in ("ppy.sh", app.settings.DOMAIN):
        for subdomain in ("c", "ce", "c4", "c5", "c6"):
            asgi_app.host(f"{subdomain}.{domain}", cho_domain.router)

        asgi_app.host(f"osu.{domain}", osu_domain.router)
        asgi_app.host(f"b.{domain}", map_domain.router)

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
