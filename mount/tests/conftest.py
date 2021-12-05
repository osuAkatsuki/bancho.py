import asyncio

import pytest
from asgi_lifespan import LifespanManager
from httpx import AsyncClient

from mount.app import services
from mount.app.api.init_api import app as asgi_app


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def database():
    async with services.database as database:
        yield database


@pytest.fixture(scope="session", autouse=True)
async def app():
    async with LifespanManager(asgi_app):
        yield asgi_app


@pytest.fixture(scope="session")
async def client(app):
    async with AsyncClient(app=app, base_url="http://localhost:1234") as client:
        yield client
