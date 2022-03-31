from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.logging import Ansi
from app.logging import log
from app.logging import magnitude_fmt_time
from app.logging import printc


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        start_time = time.perf_counter_ns()
        response = await call_next(request)
        end_time = time.perf_counter_ns()

        time_elapsed = end_time - start_time

        # TODO: add metric to datadog

        col = (
            Ansi.LGREEN
            if 200 <= response.status_code < 300
            else Ansi.LYELLOW
            if 300 <= response.status_code < 400
            else Ansi.LRED
        )

        url = f"{request.headers['host']}{request['path']}"

        log(f"[{request.method}] {response.status_code} {url}", col, end=" | ")
        printc(f"Request took: {magnitude_fmt_time(time_elapsed)}", Ansi.LBLUE)

        response.headers["process-time"] = str(round(time_elapsed) / 1e6)
        return response
