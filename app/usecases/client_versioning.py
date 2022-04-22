from __future__ import annotations

import time
from typing import Any
from typing import Literal
from typing import Mapping

import app.state.services


checkupdates_cache = {  # default timeout is 1h, set on request.
    "cuttingedge": {"check": None, "path": None, "timeout": 0},
    "stable40": {"check": None, "path": None, "timeout": 0},
    "beta40": {"check": None, "path": None, "timeout": 0},
    "stable": {"check": None, "path": None, "timeout": 0},
}


async def check_updates(
    action: Literal["check", "path", "error"],
    stream: Literal["cuttingedge", "stable40", "beta40", "stable"],
    query_params: Mapping[str, Any],
) -> bytes:
    if action == "error":
        # client is reporting an error while updating
        # TODO: handle this?
        return b""

    stream_cache = checkupdates_cache[stream]
    current_time = int(time.time())

    if stream_cache[action] and stream_cache["timeout"] > current_time:
        return stream_cache[action]

    async with app.state.services.http_client.get(
        url="https://old.ppy.sh/web/check-updates.php",
        params=query_params,
    ) as resp:
        if resp.status != 200:
            return b""  # failed to get data from osu

        result = await resp.read()

    # update the cached result.
    stream_cache[action] = result
    stream_cache["timeout"] = current_time + 3600

    return result
