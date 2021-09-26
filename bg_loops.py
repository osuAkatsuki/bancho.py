import asyncio
import time
from typing import Awaitable

from cmyui.logging import Ansi
from cmyui.logging import log

import packets
from constants.privileges import Privileges
from objects import glob

__all__ = ('initialize_housekeeping_tasks',)

async def initialize_housekeeping_tasks() -> None:
    """Create tasks for each housekeeping tasks."""
    glob.housekeeping_tasks = [
        glob.loop.create_task(task) for task in (
            _remove_expired_donation_privileges(),
            _reroll_bot_status(interval=300),
            _disconnect_ghosts(),
        )
    ]

async def _remove_expired_donation_privileges() -> list[Awaitable[None]]:
    """Remove donation privileges from users with expired sessions."""
    while True:
        log('Removing expired donation privileges.', Ansi.LMAGENTA)

        expired_donors = await glob.db.fetchall(
            'SELECT id FROM users '
            'WHERE donor_end <= UNIX_TIMESTAMP() '
            'AND priv & 48', # 48 = Supporter | Premium
            _dict=False
        )

        for expired_donor_id in expired_donors:
            p = await glob.players.get_ensure(id=expired_donor_id)

            # TODO: perhaps make a `revoke_donor` method?
            await p.remove_privs(Privileges.Donator)
            await glob.db.execute(
                'UPDATE users '
                'SET donor_end = 0 '
                'WHERE id = %s',
                [p.id]
            )

            if p.online:
                p.enqueue(packets.notification('Your supporter status has expired.'))

            log(f"{p}'s supporter status has expired.", Ansi.LMAGENTA)

        await asyncio.sleep(30 * 60) # once per 30mins

PING_TIMEOUT = 300000 // 1000 # defined by osu!
async def _disconnect_ghosts() -> None:
    """Actively disconnect users above the
       disconnection time threshold on the osu! server."""
    while True:
        await asyncio.sleep(PING_TIMEOUT // 3)
        current_time = time.time()

        for p in glob.players:
            if current_time - p.last_recv_time > PING_TIMEOUT:
                log(f'Auto-dced {p}.', Ansi.LMAGENTA)
                p.logout()


async def _reroll_bot_status(interval: int) -> None:
    """Reroll the bot's status, every `interval`."""
    while True:
        await asyncio.sleep(interval)
        packets.botStats.cache_clear()
