import asyncio
import time

import sqlalchemy
from cmyui.logging import Ansi
from cmyui.logging import log
from sqlalchemy.sql.functions import func

import app.db_models
import app.services
import packets
from app.constants.privileges import Privileges
from app.objects import glob

__all__ = ("initialize_housekeeping_tasks",)

OSU_CLIENT_MIN_PING_INTERVAL = 300000 // 1000  # defined by osu!


async def initialize_housekeeping_tasks() -> None:
    """Create tasks for each housekeeping tasks."""
    glob.housekeeping_tasks = [
        glob.loop.create_task(task)
        for task in (
            _remove_expired_donation_privileges(interval=30 * 60),
            _reroll_bot_status(interval=5 * 60),
            _disconnect_ghosts(interval=OSU_CLIENT_MIN_PING_INTERVAL // 3),
        )
    ]


async def _remove_expired_donation_privileges(interval: int) -> None:
    """Remove donation privileges from users with expired sessions."""
    while True:
        if glob.app.debug:
            log("Removing expired donation privileges.", Ansi.LMAGENTA)

        async for expired_donor in app.services.database.iterate(
            app.db_models.users.select(app.db_models.users.c.id).where(
                sqlalchemy.and_(
                    app.db_models.users.c.donor_expire_time <= func.unix_timestamp(),
                    app.db_models.users.c.priv & 48,  # 48 = Supporter | Premium
                ),
            ),
        ):
            p = await glob.players.from_cache_or_sql(id=expired_donor["id"])

            if not p:  # TODO guaranteed return method
                continue

            # TODO: perhaps make a `revoke_donor` method?
            await p.remove_privs(Privileges.DONATOR)
            await app.services.database.execute(
                app.db_models.users.update()
                .values(donor_end=0)
                .where(app.db_models.users.c.id == p.id),
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

        for p in glob.players:
            if current_time - p.last_recv_time > OSU_CLIENT_MIN_PING_INTERVAL:
                log(f"Auto-dced {p}.", Ansi.LMAGENTA)
                p.logout()


async def _reroll_bot_status(interval: int) -> None:
    """Reroll the bot's status, every `interval`."""
    while True:
        await asyncio.sleep(interval)
        packets.bot_stats.cache_clear()
