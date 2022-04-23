from __future__ import annotations

import asyncio

import databases.core

import app.utils
from app import repositories
from app.logging import Ansi
from app.logging import log
from app.objects.achievement import Achievement
from app.objects.collections import Channels
from app.objects.collections import Clans
from app.objects.collections import Matches
from app.objects.collections import Players
from app.objects.player import Player
from app.objects.player import Privileges

players = Players()
channels = Channels()
clans = Clans()
matches = Matches()
achievements: list[Achievement] = []

api_keys: dict[str, int] = {}

housekeeping_tasks: set[asyncio.Task] = set()

bot: Player


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


async def init_server_repository_caches() -> None:
    """Populate our ram cache of channels, clans, and mappools from the db."""
    await repositories.channels._populate_caches_from_database()
    await repositories.clans._populate_caches_from_database()
    await repositories.mappools._populate_caches_from_database()


async def init_server_state(db_conn: databases.core.Connection) -> None:
    """Setup & cache the global collections before listening for connections."""

    # TODO: should this be an optional thing?
    await init_server_repository_caches()

    bot_name = await app.utils.fetch_bot_name(db_conn)

    # create bot & add it to online players
    global bot
    bot = Player(
        id=1,
        name=bot_name,
        login_time=float(0x7FFFFFFF),
        last_recv_time=float(0x7FFFFFFF),
        priv=Privileges.NORMAL,
        bot_client=True,
        token=None,
    )
    players.append(bot)

    # global achievements (sorted by vn gamemodes)
    # TODO: achievements repository
    for row in await db_conn.fetch_all("SELECT * FROM achievements"):
        # NOTE: achievement conditions are stored as stringified python
        # expressions in the database to allow for extensive customizability.
        row = dict(row)
        condition = eval(f'lambda score, mode_vn: {row.pop("cond")}')
        achievement = Achievement(**row, condition=condition)

        achievements.append(achievement)

    # static api keys
    global api_keys
    api_keys = {
        row["api_key"]: row["id"]
        for row in await db_conn.fetch_all(
            "SELECT id, api_key FROM users WHERE api_key IS NOT NULL",
        )
    }
