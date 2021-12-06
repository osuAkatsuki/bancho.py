import asyncio
import time

import sqlalchemy
from cmyui.logging import Ansi
from cmyui.logging import log
from sqlalchemy.sql.functions import func

import packets
from mount.app import db_models
from mount.app import services
from mount.app import sessions
from mount.app import settings
from mount.app.constants.privileges import Privileges

__all__ = ("initialize_housekeeping_tasks",)

OSU_CLIENT_MIN_PING_INTERVAL = 300000 // 1000  # defined by osu!


async def initialize_housekeeping_tasks() -> list[asyncio.Task]:
    """Create tasks for each housekeeping tasks."""
    loop = asyncio.get_running_loop()

    return [
        loop.create_task(coro)
        for coro in (
            _remove_expired_donation_privileges(interval=30 * 60),
            _reroll_bot_status(interval=5 * 60),
            _disconnect_ghosts(interval=OSU_CLIENT_MIN_PING_INTERVAL // 3),
        )
    ]


def _handle_fut_exception(fut: asyncio.Future) -> None:
    if not fut.cancelled():
        if exception := fut.exception():
            loop = asyncio.get_running_loop()
            loop.call_exception_handler(
                {
                    "message": "unhandled exception during loop shutdown",
                    "exception": exception,
                    "task": fut,
                },
            )


async def cancel_tasks(tasks: list[asyncio.Task]) -> None:
    """Cancel & handle exceptions for a list of tasks."""
    for task in tasks:
        task.cancel()

    await asyncio.gather(*tasks, return_exceptions=True)

    for task in tasks:
        _handle_fut_exception(task)


async def _remove_expired_donation_privileges(interval: int) -> None:
    """Remove donation privileges from users with expired sessions."""
    while True:
        if settings.DEBUG:
            log("Removing expired donation privileges.", Ansi.LMAGENTA)

        async for expired_donor in services.database.iterate(
            db_models.users.select(db_models.users.c.id).where(
                sqlalchemy.and_(
                    db_models.users.c.donor_end <= func.unix_timestamp(),
                    db_models.users.c.priv.op("&")(48) == 48,  # Supporter | Premium
                ),
            ),
        ):
            p = await sessions.players.from_cache_or_sql(id=expired_donor["id"])

            if not p:  # TODO guaranteed return method
                continue

            # TODO: perhaps make a `revoke_donor` method?
            await p.remove_privs(Privileges.DONATOR)
            await services.database.execute(
                db_models.users.update()
                .values(donor_end=0)
                .where(db_models.users.c.id == p.id),
            )

            if p.online:
                p.enqueue(packets.notification("Your supporter status has expired."))

            log(f"{p}'s supporter status has expired.", Ansi.LMAGENTA)

        await asyncio.sleep(interval)


async def _disconnect_ghosts(interval: int) -> None:
    """Actively disconnect users above the
    disconnection time threshold on the osu! server."""
    while True:
        await asyncio.sleep(interval)
        current_time = time.time()

        for p in sessions.players:
            if current_time - p.last_recv_time > OSU_CLIENT_MIN_PING_INTERVAL:
                log(f"Auto-dced {p}.", Ansi.LMAGENTA)
                p.logout()


async def _reroll_bot_status(interval: int) -> None:
    """Reroll the bot's status, every `interval`."""
    while True:
        await asyncio.sleep(interval)
        # packets.bot_stats.cache_clear()
