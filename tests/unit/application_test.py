from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from app.application import RuntimeResources
from app.application import managed_runtime_resources


class _FakeDatabase:
    def __init__(self, events: list[str], *, fail_connect: bool = False) -> None:
        self.events = events
        self.fail_connect = fail_connect

    async def connect(self) -> None:
        self.events.append("database.connect")
        if self.fail_connect:
            raise RuntimeError("database connection failed")

    async def disconnect(self) -> None:
        self.events.append("database.disconnect")


class _FakeRedis:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def initialize(self) -> None:
        self.events.append("redis.initialize")

    async def aclose(self) -> None:
        self.events.append("redis.aclose")


class _FakeHttpClient:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def aclose(self) -> None:
        self.events.append("http.aclose")


class _FakeDatadog:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def start(self, *, flush_in_thread: bool, flush_interval: int) -> None:
        self.events.append("datadog.start")

    def gauge(self, metric: str, value: int) -> None:
        self.events.append("datadog.gauge")

    def stop(self) -> None:
        self.events.append("datadog.stop")

    def flush(self) -> None:
        self.events.append("datadog.flush")


def _resources(
    events: list[str],
    *,
    fail_database_connect: bool = False,
    with_datadog: bool = False,
) -> RuntimeResources:
    return cast(
        RuntimeResources,
        SimpleNamespace(
            database=_FakeDatabase(events, fail_connect=fail_database_connect),
            redis=_FakeRedis(events),
            http_client=_FakeHttpClient(events),
            datadog=_FakeDatadog(events) if with_datadog else None,
        ),
    )


async def test_runtime_resources_close_when_application_composition_fails() -> None:
    events: list[str] = []

    with pytest.raises(RuntimeError, match="composition failed"):
        async with managed_runtime_resources(_resources(events, with_datadog=True)):
            raise RuntimeError("composition failed")

    assert events == [
        "database.connect",
        "redis.initialize",
        "datadog.start",
        "datadog.gauge",
        "datadog.stop",
        "datadog.flush",
        "database.disconnect",
        "redis.aclose",
        "http.aclose",
    ]


async def test_runtime_resources_close_after_partial_connection_failure() -> None:
    events: list[str] = []

    with pytest.raises(RuntimeError, match="database connection failed"):
        async with managed_runtime_resources(
            _resources(events, fail_database_connect=True),
        ):
            raise AssertionError("startup should not reach the application builder")

    assert events == [
        "database.connect",
        "database.disconnect",
        "redis.aclose",
        "http.aclose",
    ]
