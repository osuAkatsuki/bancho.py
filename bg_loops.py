import asyncio
import time
from typing import Coroutine

from cmyui.logging import Ansi
from cmyui.logging import log

import packets
from constants.privileges import Privileges
from objects import glob

__all__ = ('initialize_tasks',)

async def initialize_tasks() -> None:
    glob.housekeeping_tasks = [
        glob.loop.create_task(task) for task in (
            *(t for t in await _donor_expiry()),
            _reroll_bot_status(interval=300),
            _disconnect_ghosts(),
        )
    ]

async def _donor_expiry() -> list[Coroutine[None, None, None]]:
    """Add new donation ranks & enqueue tasks to remove current ones."""
    # TODO: this system can get quite a bit better; rather than just
    # removing, it should rather update with the new perks (potentially
    # a different tier, enqueued after their current perks).

    async def rm_donor(userid: int, when: int):
        if (delta := when - time.time()) >= 0:
            await asyncio.sleep(delta)

        p = await glob.players.get_ensure(id=userid)

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

    # enqueue rm_donor for any supporter
    # expiring in the next 30 days.
    # TODO: perhaps donor_end datetime?
    async with glob.db.pool.acquire() as conn:
        async with conn.cursor() as db_cursor:
            await db_cursor.execute(
                'SELECT id AS userid, donor_end AS `when` FROM users '
                'WHERE donor_end <= UNIX_TIMESTAMP() + (60 * 60 * 24 * 7 * 4) '
                #'WHERE donor_end < DATE_ADD(NOW(), INTERVAL 30 DAY) '
                'AND priv & 48' # 48 = Supporter | Premium
            )

            return [rm_donor(**donation) async for donation in db_cursor]

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
