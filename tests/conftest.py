from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
import respx
from asgi_lifespan import LifespanManager
from asgi_lifespan._types import ASGIApp
from fastapi import status

from app.api.init_api import asgi_app

# TODO: fixtures for postgres database connection(s) for itests

# TODO: I believe if we switch to fastapi.TestClient, we
# will no longer need to use the asgi-lifespan dependency.
# (We do not need an asynchronous http client for our tests)


@pytest.fixture(autouse=True)
def mock_out_initial_image_downloads(respx_mock: respx.MockRouter) -> None:
    # mock out default avatar download
    respx_mock.get(url__regex=r"https://i.cmyui.xyz/U24XBZw-4wjVME-JaEz3.png").mock(
        return_value=httpx.Response(
            status_code=status.HTTP_200_OK,
            headers={"Content-Type": "image/png"},
            content=b"i am a png file",
        ),
    )
    # mock out achievement image downloads
    respx_mock.get(url__regex=r"https://assets.ppy.sh/medals/client/.+").mock(
        return_value=httpx.Response(
            status_code=status.HTTP_200_OK,
            headers={"Content-Type": "image/png"},
            content=b"i am a png file",
        ),
    )


@pytest.fixture
async def app() -> AsyncIterator[ASGIApp]:
    async with LifespanManager(
        asgi_app,
        startup_timeout=None,
        shutdown_timeout=None,
    ) as manager:
        yield manager.app


@pytest.fixture
async def http_client(app: ASGIApp) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        yield client


pytest_plugins = []
