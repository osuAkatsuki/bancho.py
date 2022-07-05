from __future__ import annotations

import asyncio
import logging
import time

import app.packets
import app.settings
import app.state
from app import repositories
from app import usecases
from app.constants.privileges import Privileges

__all__ = ("initialize_housekeeping_tasks",)

OSU_CLIENT_MIN_PING_INTERVAL = 300000 // 1000  # defined by osu!


async def initialize_housekeeping_tasks() -> None:
    """Create tasks for each housekeeping tasks."""
    logging.info("Initializing housekeeping tasks.")

    loop = asyncio.get_running_loop()

    app.state.sessions.housekeeping_tasks.update(
        {
            loop.create_task(task)
            for task in (
                _remove_expired_donation_privileges(interval=30 * 60),
                _update_bot_status(interval=5 * 60),
                _disconnect_ghosts(interval=OSU_CLIENT_MIN_PING_INTERVAL // 3),
            )
        },
    )


async def _remove_expired_donation_privileges(interval: int) -> None:
    """Remove donation privileges from users with expired sessions."""
    while True:
        logging.debug("Removing expired donation privileges.")

        expired_donors = await app.state.services.database.fetch_all(
            "SELECT id FROM users "
            "WHERE donor_end <= UNIX_TIMESTAMP() "
            "AND priv & 48",  # 48 = Supporter | Premium
        )

        for expired_donor in expired_donors:
            player = await repositories.players.fetch_by_id(expired_donor["id"])
            assert player is not None

            await usecases.players.remove_privileges(player, Privileges.DONATOR)
            await usecases.players.reset_donator_time(player)

            if player.online:
                player.enqueue(
                    app.packets.notification("Your supporter status has expired."),
                )

            logging.info(f"{player}'s supporter status has expired.")

        await asyncio.sleep(interval)


async def _disconnect_ghosts(interval: int) -> None:
    """Actively disconnect users above the
    disconnection time threshold on the osu! server."""
    while True:
        await asyncio.sleep(interval)
        current_time = time.time()

        for player in app.state.sessions.players:
            if current_time - player.last_recv_time > OSU_CLIENT_MIN_PING_INTERVAL:
                logging.info(f"Auto-dced {player}.")
                await usecases.players.logout(player)


async def _update_bot_status(interval: int) -> None:
    """Reroll the bot's status, every `interval`."""
    while True:
        await asyncio.sleep(interval)
        app.packets.bot_stats.cache_clear()
