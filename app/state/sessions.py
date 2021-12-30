import asyncio
from typing import TYPE_CHECKING

from cmyui.logging import Ansi
from cmyui.logging import log

from app.objects.collections import Channels
from app.objects.collections import Clans
from app.objects.collections import MapPools
from app.objects.collections import Matches
from app.objects.collections import Players

if TYPE_CHECKING:
    from app.objects.achievement import Achievement
    from app.objects.player import Player

players = Players()
channels = Channels()
pools = MapPools()
clans = Clans()
matches = Matches()
achievements: list["Achievement"] = []

api_keys = {}

housekeeping_tasks: set[asyncio.Task] = set()

bot: "Player"


# usecases


async def cancel_housekeeping_tasks() -> None:
    log(
        f"-> Cancelling {len(housekeeping_tasks)} housekeeping tasks.",
        Ansi.LMAGENTA,
    )

    # cancel housekeeping tasks
    for task in housekeeping_tasks:
        task.cancel()

    await asyncio.gather(*housekeeping_tasks, return_exceptions=True)

    loop = asyncio.get_running_loop()

    for task in housekeeping_tasks:
        if not task.cancelled():
            if exception := task.exception():
                loop.call_exception_handler(
                    {
                        "message": "unhandled exception during loop shutdown",
                        "exception": exception,
                        "task": task,
                    },
                )
