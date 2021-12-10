from contextlib import asynccontextmanager
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from typing import AsyncIterator
from typing import Iterator
from typing import Optional

import aiohttp
import aioredis
import cmyui
import datadog
import geoip2.database
import orjson


@asynccontextmanager
async def acquire_http_session(
    has_internet: bool,
) -> AsyncIterator[Optional[aiohttp.ClientSession]]:
    if has_internet:
        # TODO: perhaps a config setting to enable optimizations like this?
        json_encoder = lambda x: str(orjson.dumps(x))

        http_sess = aiohttp.ClientSession(json_serialize=json_encoder)
        try:
            yield http_sess
        finally:
            await http_sess.close()


@asynccontextmanager
async def acquire_mysql_db_pool(
    config: dict[str, Any],
) -> AsyncIterator[Optional[cmyui.AsyncSQLPool]]:
    db_pool = cmyui.AsyncSQLPool()
    try:
        await db_pool.connect(config)
        yield db_pool
    finally:
        await db_pool.close()


@asynccontextmanager
async def acquire_redis_db_pool() -> AsyncIterator[Optional[aioredis.Redis]]:
    try:
        db_pool = await aioredis.from_url("redis://localhost")
        yield db_pool
    finally:
        await db_pool.close()


@contextmanager
def acquire_geoloc_db_conn(db_file: Path) -> Iterator[Optional[geoip2.database.Reader]]:
    if db_file.exists():
        geoloc_db = geoip2.database.Reader(str(db_file))
        try:
            yield geoloc_db
        finally:
            geoloc_db.close()
    else:
        yield None


@contextmanager
def acquire_datadog_client(
    config: dict[str, Any],
) -> Iterator[Optional[datadog.ThreadStats]]:
    if all(config.values()):
        datadog.initialize(**config)
        datadog_client = datadog.ThreadStats()
        try:
            datadog_client.start(flush_in_thread=True, flush_interval=15)
            # wipe any previous stats from the page.
            datadog_client.gauge("gulag.online_players", 0)
            yield datadog_client
        finally:
            datadog_client.stop()
            datadog_client.flush()
    else:
        yield None
