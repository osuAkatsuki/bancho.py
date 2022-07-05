from __future__ import annotations

import asyncio
import logging

import databases.core

import app.state.services
import app.utils
from app import repositories
from app.objects.collections import Matches
from app.objects.collections import Players
from app.objects.player import Player
from app.objects.player import Privileges

players = Players()
matches = Matches()

api_keys: dict[str, int] = {}

housekeeping_tasks: set[asyncio.Task] = set()

bot: Player


# usecases


async def cancel_housekeeping_tasks() -> None:
    logging.info(f"-> Cancelling {len(housekeeping_tasks)} housekeeping tasks.")

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
    for repository in (
        repositories.channels,
        repositories.clans,
        repositories.mappools,
        repositories.network_adapters,
        repositories.achievements,
    ):
        for resource in await repository.fetch_all():
            repository.add_to_cache(resource)  # type: ignore


async def populate_redis_overall_rankings() -> None:
    """Calculate global and country rankings for all modes."""
    for mode in (0, 1, 2, 3, 4, 5, 6, 8):
        rows = await app.state.services.database.fetch_all(
            "SELECT users.id, users.country, stats.pp "
            "FROM users "
            "INNER JOIN stats ON users.id = stats.id "
            "WHERE mode = :mode AND users.priv & 1",
            {"mode": mode},
        )
        for row in rows:
            await app.state.services.redis.zadd(
                f"bancho:leaderboard:{mode}",
                {str(row["id"]): row["pp"]},
            )

            # country rank
            await app.state.services.redis.zadd(
                f"bancho:leaderboard:{mode}:{row['country']}",
                {str(row["id"]): row["pp"]},
            )


async def init_server_state(db_conn: databases.core.Connection) -> None:
    """Setup & cache the global collections before listening for connections."""

    # TODO: should this be an optional thing?
    await init_server_repository_caches()

    await populate_redis_overall_rankings()

    bot_name = await app.utils.fetch_bot_name(db_conn)

    # create bot & add it to online players
    # TODO: clean this up to just use normal repositories functions?
    global bot
    bot = Player(
        id=1,
        name=bot_name,
        login_time=float(0x7FFFFFFF),
        last_recv_time=float(0x7FFFFFFF),
        priv=Privileges.UNRESTRICTED,
        bot_client=True,
        token=None,
    )
    repositories.players.id_cache[bot.id] = bot
    repositories.players.safe_name_cache[bot.safe_name] = bot
    players.append(bot)

    # static api keys
    global api_keys
    api_keys = {
        row["api_key"]: row["id"]
        for row in await db_conn.fetch_all(
            "SELECT id, api_key FROM users WHERE api_key IS NOT NULL",
        )
    }
