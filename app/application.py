from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from collections.abc import Coroutine
from contextlib import AsyncExitStack
from contextlib import asynccontextmanager
from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING
from typing import Any

import datadog as datadog_module
import datadog.threadstats.base as datadog_client
import httpx
from redis import asyncio as aioredis
from redis.asyncio import Redis

import app.settings
from app.adapters.database import Database
from app.caches import ApplicationCaches
from app.repositories.container import Repositories
from app.service_container import ApplicationServices
from app.sessions import SessionState
from app.runtime import IPResolver

if TYPE_CHECKING:
    from app.bancho.router import BanchoPacketRouter
    from app.command_router import CommandRouter


@dataclass(frozen=True)
class RuntimeResources:
    database: Database
    redis: Redis
    http_client: httpx.AsyncClient
    datadog: datadog_client.ThreadStats | None
    ip_resolver: IPResolver
    loop: asyncio.AbstractEventLoop


def build_runtime_resources(
    loop: asyncio.AbstractEventLoop,
) -> RuntimeResources:
    datadog: datadog_client.ThreadStats | None = None
    if str(app.settings.DATADOG_API_KEY) and str(app.settings.DATADOG_APP_KEY):
        datadog_module.initialize(
            api_key=str(app.settings.DATADOG_API_KEY),
            app_key=str(app.settings.DATADOG_APP_KEY),
        )
        datadog = datadog_client.ThreadStats()  # type: ignore[no-untyped-call]

    return RuntimeResources(
        database=Database(app.settings.DB_DSN),
        redis=aioredis.from_url(app.settings.REDIS_DSN),
        http_client=httpx.AsyncClient(),
        datadog=datadog,
        ip_resolver=IPResolver(),
        loop=loop,
    )


def _stop_datadog(datadog: datadog_client.ThreadStats) -> None:
    datadog.stop()  # type: ignore[no-untyped-call]
    datadog.flush()  # type: ignore[no-untyped-call]


@asynccontextmanager
async def managed_runtime_resources(
    resources: RuntimeResources,
) -> AsyncIterator[None]:
    """Open runtime infrastructure and always release partial startup state."""
    async with AsyncExitStack() as cleanup:
        cleanup.push_async_callback(resources.http_client.aclose)
        cleanup.push_async_callback(resources.redis.aclose)
        cleanup.push_async_callback(resources.database.disconnect)

        await resources.database.connect()
        await resources.redis.initialize()  # type: ignore[unused-awaitable]

        if resources.datadog is not None:
            cleanup.callback(_stop_datadog, resources.datadog)
            resources.datadog.start(  # type: ignore[no-untyped-call]
                flush_in_thread=True,
                flush_interval=15,
            )
            resources.datadog.gauge(  # type: ignore[no-untyped-call]
                "bancho.online_players",
                0,
            )

        yield


@dataclass
class BackgroundTaskSupervisor:
    """Own fire-and-forget tasks for one application lifecycle."""

    loop: asyncio.AbstractEventLoop
    tasks: set[asyncio.Task[object]] = field(default_factory=set)

    def schedule(self, coroutine: Coroutine[Any, Any, object]) -> None:
        task = self.loop.create_task(coroutine)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)


@dataclass
class Application:
    """The complete object graph for one running application.

    This aggregate belongs to the composition/framework boundary. Application
    code receives exact members from it rather than receiving Application.
    """

    resources: RuntimeResources
    caches: ApplicationCaches
    sessions: SessionState
    repositories: Repositories
    services: ApplicationServices
    command_router: CommandRouter
    packet_router: BanchoPacketRouter
    score_submission_locks: defaultdict[str, asyncio.Lock]
    background_tasks: BackgroundTaskSupervisor
