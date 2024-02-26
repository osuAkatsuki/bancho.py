from __future__ import annotations

import dataclasses
import hashlib
import json
import platform
import time
from dataclasses import dataclass
from typing import Any

import psutil
from httpx import AsyncClient
from tenacity import retry
from tenacity.stop import stop_after_attempt

from app import settings

MIN_SLOW_QUERY_SECONDS = 5.0

HTTP_CLIENT = AsyncClient()


@dataclass
class SoftwareInfo:
    version: str
    domain: str


@dataclass
class SystemInfo:
    system: str
    node: str
    release: str
    version: str
    machine: str
    processor: str


@dataclass
class LanguageInfo:
    python_version: str
    build_no: str
    build_date: str
    python_compiler: str
    python_implementation: str


@dataclass
class SystemLoadInfo:
    cpu_1min_average: float
    cpu_5min_average: float
    cpu_15min_average: float


@dataclass
class TelemetryEventReport:
    software_info: SoftwareInfo
    system_info: SystemInfo
    language_info: LanguageInfo
    system_load_info: SystemLoadInfo
    event_data: dict[str, Any]


@retry(reraise=True, stop=stop_after_attempt(3))
async def report_event(event_data: dict[str, Any]) -> None:
    cpu_1min_average, cpu_5min_average, cpu_15min_average = psutil.getloadavg()
    event = TelemetryEventReport(
        software_info=SoftwareInfo(
            version=settings.VERSION,
            domain=settings.DOMAIN,
        ),
        system_info=SystemInfo(
            system=platform.system(),
            node=platform.node(),
            release=platform.release(),
            version=platform.version(),
            machine=platform.machine(),
            processor=platform.processor(),
        ),
        language_info=LanguageInfo(
            python_version=platform.python_version(),
            build_no=platform.python_build()[0],
            build_date=platform.python_build()[1],
            python_compiler=platform.python_compiler(),
            python_implementation=platform.python_implementation(),
        ),
        system_load_info=SystemLoadInfo(
            cpu_1min_average=cpu_1min_average,
            cpu_5min_average=cpu_5min_average,
            cpu_15min_average=cpu_15min_average,
        ),
        event_data=event_data,
    )
    request_data = dataclasses.asdict(event)
    idempotency_key = hashlib.sha256(
        json.dumps(request_data, sort_keys=True).encode("utf-8"),
    ).hexdigest()
    response = await HTTP_CLIENT.post(
        url="https://telemetry.cmyui.xyz/report",
        headers={"Idempotency-Key": idempotency_key},
        json=request_data,
    )
    response.raise_for_status()
    return None


def hook_database_calls() -> None:
    def _wrap_database_call(func):
        async def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            response = await func(*args, **kwargs)
            end_time = time.perf_counter()

            seconds_elapsed = end_time - start_time

            if seconds_elapsed >= MIN_SLOW_QUERY_SECONDS:
                event_data = {
                    "query": kwargs.get("query", args and args[0]),
                    "seconds_elapsed": seconds_elapsed,
                }
                await report_event(event_data)

            return response

        return wrapper

    import app.state.services

    for attr in ("execute", "execute_many", "fetch_one", "fetch_all"):
        unwrapped_func = getattr(app.state.services.database, attr)
        wrapped_func = _wrap_database_call(unwrapped_func)
        setattr(app.state.services.database, attr, wrapped_func)

    return None
