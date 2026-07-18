from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

import app.packets
from app.constants.privileges import Privileges
from app.logging import Ansi
from app.logging import log
from app.objects.player import Player
from app.repositories.leaderboard_ranks import LeaderboardRanksRepository
from app.repositories.logs import LogsRepository
from app.repositories.users import UsersRepository
from app.services.player_data import PlayerDataService
from app.services.player_sessions import PlayerSessionService

MODES_WITH_LEADERBOARDS = (0, 1, 2, 3, 4, 5, 6, 8)


@dataclass(frozen=True)
class PlayerModerationService:
    users: UsersRepository
    logs: LogsRepository
    leaderboard_ranks: LeaderboardRanksRepository
    player_data: PlayerDataService
    player_sessions: PlayerSessionService
    broadcast_packet: Callable[[bytes], None]
    send_audit_log: Callable[[str], None]
    current_time: Callable[[], float] = time.time

    async def set_privileges(self, player: Player, privileges: Privileges) -> None:
        player.priv = privileges
        vars(player).pop("bancho_priv", None)
        await self.users.partial_update(id=player.id, priv=int(player.priv))

    async def add_privileges(self, player: Player, bits: Privileges) -> None:
        await self.set_privileges(player, player.priv | bits)
        if player.is_online:
            player.enqueue(app.packets.bancho_privileges(player.bancho_priv))

    async def remove_privileges(self, player: Player, bits: Privileges) -> None:
        await self.set_privileges(player, player.priv & ~bits)
        if player.is_online:
            player.enqueue(app.packets.bancho_privileges(player.bancho_priv))

    async def restrict(
        self,
        player: Player,
        *,
        admin: Player,
        reason: str,
    ) -> None:
        await self.remove_privileges(player, Privileges.UNRESTRICTED)
        await self.logs.create(
            _from=admin.id,
            to=player.id,
            action="restrict",
            msg=reason,
        )

        country = player.geoloc["country"]["acronym"]
        for mode in MODES_WITH_LEADERBOARDS:
            await self.leaderboard_ranks.remove_from_global_leaderboard(
                player.id,
                mode,
            )
            await self.leaderboard_ranks.remove_from_country_leaderboard(
                player.id,
                mode,
                country,
            )

        message = f"{admin} restricted {player} for: {reason}."
        log(message, Ansi.LRED)
        self.send_audit_log(message)
        if player.is_online:
            self.player_sessions.logout(player)

    async def unrestrict(
        self,
        player: Player,
        *,
        admin: Player,
        reason: str,
    ) -> None:
        await self.add_privileges(player, Privileges.UNRESTRICTED)
        await self.logs.create(
            _from=admin.id,
            to=player.id,
            action="unrestrict",
            msg=reason,
        )

        if not player.is_online:
            await self.player_data.hydrate_stats(player)

        country = player.geoloc["country"]["acronym"]
        for mode, stats in player.stats.items():
            await self.leaderboard_ranks.add_to_global_leaderboard(
                player.id,
                mode.value,
                stats.pp,
            )
            await self.leaderboard_ranks.add_to_country_leaderboard(
                player.id,
                mode.value,
                country,
                stats.pp,
            )

        message = f"{admin} unrestricted {player} for: {reason}."
        log(message, Ansi.LRED)
        self.send_audit_log(message)
        if player.is_online:
            self.player_sessions.logout(player)

    async def silence(
        self,
        player: Player,
        *,
        admin: Player,
        duration: float,
        reason: str,
    ) -> None:
        player.silence_end = int(self.current_time() + duration)
        await self.users.partial_update(id=player.id, silence_end=player.silence_end)
        await self.logs.create(
            _from=admin.id,
            to=player.id,
            action="silence",
            msg=reason,
        )

        player.enqueue(app.packets.silence_end(int(duration)))
        self.broadcast_packet(app.packets.user_silenced(player.id))
        if player.match:
            self.player_sessions.leave_match(player)
        log(f"Silenced {player}.", Ansi.LCYAN)

    async def unsilence(
        self,
        player: Player,
        *,
        admin: Player,
        reason: str,
    ) -> None:
        player.silence_end = int(self.current_time())
        await self.users.partial_update(id=player.id, silence_end=player.silence_end)
        await self.logs.create(
            _from=admin.id,
            to=player.id,
            action="unsilence",
            msg=reason,
        )
        player.enqueue(app.packets.silence_end(0))
        log(f"Unsilenced {player}.", Ansi.LCYAN)
