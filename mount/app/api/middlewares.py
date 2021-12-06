import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        start_time = time.perf_counter_ns()
        response = await call_next(request)
        end_time = time.perf_counter_ns()

        time_elapsed = round((end_time - start_time) / 1e6)

        # TODO: add metric to datadog
        print(f'{request.headers["host"]}{request["path"]} took {time_elapsed:.2f}ms')

        response.headers["process-time"] = str(time_elapsed)
        return response
