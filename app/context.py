from contextlib import asynccontextmanager
from contextlib import contextmanager
from pathlib import Path
from typing import AsyncIterator
from typing import Iterator
from typing import Optional

import aiohttp
import aioredis
import databases
import datadog as datadog_module
import datadog.threadstats.base as datadog_client
import geoip2.database
import orjson

import app.settings
import app.state


@asynccontextmanager
async def acquire_http_session() -> AsyncIterator[aiohttp.ClientSession]:
    # TODO: perhaps a config setting to enable optimizations like this?
    json_encoder = lambda x: str(orjson.dumps(x))

    http_sess = aiohttp.ClientSession(json_serialize=json_encoder)
    try:
        yield http_sess
    finally:
        await http_sess.close()


@asynccontextmanager
async def acquire_mysql_db_pool() -> AsyncIterator[databases.Database]:
    async with databases.Database(app.settings.DB_DSN) as db_pool:
        yield db_pool


@asynccontextmanager
async def acquire_redis_db_pool() -> AsyncIterator[aioredis.Redis]:
    db_pool: aioredis.Redis = await aioredis.from_url(app.settings.REDIS_DSN)
    try:
        yield db_pool
    finally:
        await db_pool.close()


GEOLOC_DB_FILE = Path.cwd() / "ext/GeoLite2-City.mmdb"


@contextmanager
def acquire_geoloc_db_conn() -> Iterator[Optional[geoip2.database.Reader]]:
    if GEOLOC_DB_FILE.exists():
        geoloc_db = geoip2.database.Reader(GEOLOC_DB_FILE)
        try:
            yield geoloc_db
        finally:
            geoloc_db.close()
    else:
        yield None


@contextmanager
def acquire_datadog_client() -> Iterator[Optional[datadog_client.ThreadStats]]:
    if app.settings.DATADOG_API_KEY and app.settings.DATADOG_APP_KEY:
        datadog_module.initialize(
            api_key=app.settings.DATADOG_API_KEY,
            app_key=app.settings.DATADOG_APP_KEY,
        )
        datadog = datadog_client.ThreadStats()

        datadog.start(flush_in_thread=True, flush_interval=15)

        # wipe any previous stats from the page.
        datadog.gauge("gulag.online_players", 0)
        try:
            yield datadog
        finally:
            datadog.stop()
            datadog.flush()
    else:
        yield None
