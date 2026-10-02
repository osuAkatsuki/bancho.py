from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Collection
from dataclasses import dataclass

from app.constants.privileges import Privileges
from app.logging import Ansi
from app.logging import log
from app.objects.player import Player
from app.repositories.users import UsersRepository

OSU_CLIENT_MIN_PING_INTERVAL = 300000 // 1000  # defined by osu!
SUPPORTER_EXPIRATION_INTERVAL = 30 * 60
BOT_STATUS_UPDATE_INTERVAL = 5 * 60
GHOST_DISCONNECT_INTERVAL = OSU_CLIENT_MIN_PING_INTERVAL // 3
SUPPORTER_EXPIRED_NOTIFICATION = "Your supporter status has expired."

PlayerFetcher = Callable[[int], Awaitable[Player | None]]
PrivilegeRemover = Callable[[Player, Privileges], Awaitable[None]]
PlayerNotifier = Callable[[Player, str], None]
PlayerLogout = Callable[[Player], None]
Sleep = Callable[[float], Awaitable[None]]


@dataclass(frozen=True)
class HousekeepingService:
    """One-shot housekeeping actions for one application graph."""

    users: UsersRepository
    online_players: Collection[Player]
    fetch_player: PlayerFetcher
    remove_privileges: PrivilegeRemover
    notify_player: PlayerNotifier
    logout_player: PlayerLogout
    clear_bot_status_cache: Callable[[], None]
    current_time: Callable[[], float]
    debug: bool

    async def expire_donation_privileges_once(self) -> None:
        """Remove supporter privileges whose persisted expiry has passed."""
        if self.debug:
            log("Removing expired donation privileges.", Ansi.LMAGENTA)

        for player_id in await self.users.fetch_expired_donor_ids():
            player = await self.fetch_player(player_id)
            assert player is not None

            await self.remove_privileges(player, Privileges.DONATOR)
            player.donor_end = 0
            await self.users.partial_update(id=player.id, donor_end=0)

            if player.is_online:
                self.notify_player(player, SUPPORTER_EXPIRED_NOTIFICATION)

            log(f"{player}'s supporter status has expired.", Ansi.LMAGENTA)

    async def disconnect_ghosts_once(self) -> None:
        """Disconnect online players beyond the client ping timeout."""
        current_time = self.current_time()
        for player in self.online_players:
            if current_time - player.last_recv_time > OSU_CLIENT_MIN_PING_INTERVAL:
                log(f"Auto-dced {player}.", Ansi.LMAGENTA)
                self.logout_player(player)

    async def refresh_bot_status_once(self) -> None:
        """Invalidate the cached bot status so it is re-rolled on next use."""
        self.clear_bot_status_cache()


async def run_periodically(
    action: Callable[[], Awaitable[None]],
    *,
    interval: float,
    initial_delay: float = 0,
    sleep: Sleep = asyncio.sleep,
) -> None:
    """Run an injected action until the owning task is cancelled."""
    if initial_delay:
        await sleep(initial_delay)

    while True:
        await action()
        await sleep(interval)
