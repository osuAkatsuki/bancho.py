from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from asgi_lifespan import LifespanManager
from asgi_lifespan._types import ASGIApp

from app.api.init_api import asgi_app

# TODO: fixtures for postgres database connection(s) for itests

# TODO: I believe if we switch to fastapi.TestClient, we
# will no longer need to use the asgi-lifespan dependency.
# (We do not need an asynchronous http client for our tests)


@pytest.fixture
async def app() -> AsyncIterator[ASGIApp]:
    async with LifespanManager(asgi_app) as manager:
        yield manager.app


pytest_plugins = []
