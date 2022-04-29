from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import databases
import pytest
from asgi_lifespan import LifespanManager

import app.settings
import app.state.services
import app.state.sessions
import app.utils
from app.api.init_api import asgi_app

if TYPE_CHECKING:
    pass

# scopes = ["session", "package", "module", "class", "function"]


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def setup_app():
    # temporarily start up db to create database & tables
    async with databases.Database(app.settings.TEST_DB_DSN) as temp_db:
        await temp_db.execute("DROP DATABASE IF EXISTS bancho_test")
        await temp_db.execute("CREATE DATABASE bancho_test")
        await temp_db.execute("USE bancho_test")

        # run migration & seeding stack
        with open("migrations/base.sql") as f:
            await temp_db.execute(f.read())

    # overwrite database connection backend
    # with one pointing at our new test db
    app.state.services.database = databases.Database(
        f"{app.settings.TEST_DB_DSN}bancho_test",
        # force_rollback=True,
    )

    # run all tests in the normal server runtime environment
    async with LifespanManager(asgi_app):
        yield asgi_app

    # tear down the test database
    async with app.state.services.database:
        await app.state.services.database.execute("DROP DATABASE bancho_test")


# @pytest.fixture(scope="session")
# async def client(app):
#     async with AsyncClient(app=app, base_url="http://localhost:10300") as client:
#         yield client
