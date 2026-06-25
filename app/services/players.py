from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.objects.player import Player
from app.repositories.stats import Stat
from app.repositories.stats import StatsRepository
from app.repositories.users import User
from app.repositories.users import UsersRepository


class OnlinePlayers(Protocol):
    def get(
        self,
        token: str | None = None,
        id: int | None = None,
        name: str | None = None,
    ) -> Player | None: ...


@dataclass(frozen=True)
class PlayerStatus:
    login_time: int
    action: int
    info_text: str
    mode: int
    mods: int
    beatmap_id: int


@dataclass(frozen=True)
class PlayersListing:
    players: list[User]
    total_players: int


@dataclass(frozen=True)
class PlayerStatsListing:
    stats: list[Stat]
    total_stats: int


@dataclass(frozen=True)
class PlayersService:
    users: UsersRepository
    stats: StatsRepository
    online_players: OnlinePlayers

    async def fetch_players(
        self,
        *,
        priv: int | None,
        country: str | None,
        clan_id: int | None,
        clan_priv: int | None,
        preferred_mode: int | None,
        play_style: int | None,
        page: int,
        page_size: int,
    ) -> PlayersListing:
        players = await self.users.fetch_many(
            priv=priv,
            country=country,
            clan_id=clan_id,
            clan_priv=clan_priv,
            preferred_mode=preferred_mode,
            play_style=play_style,
            page=page,
            page_size=page_size,
        )
        total_players = await self.users.fetch_count(
            priv=priv,
            country=country,
            clan_id=clan_id,
            clan_priv=clan_priv,
            preferred_mode=preferred_mode,
            play_style=play_style,
        )

        return PlayersListing(players=players, total_players=total_players)

    async def fetch_player(self, player_id: int) -> User | None:
        return await self.users.fetch_one(id=player_id)

    def fetch_player_status(self, player_id: int) -> PlayerStatus | None:
        player = self.online_players.get(id=player_id)
        if player is None:
            return None

        return PlayerStatus(
            login_time=int(player.login_time),
            action=int(player.status.action),
            info_text=player.status.info_text,
            mode=int(player.status.mode),
            mods=int(player.status.mods),
            beatmap_id=player.status.map_id,
        )

    async def fetch_player_mode_stats(
        self,
        *,
        player_id: int,
        mode: int,
    ) -> Stat | None:
        return await self.stats.fetch_one(player_id, mode)

    async def fetch_player_stats(
        self,
        *,
        player_id: int,
        page: int,
        page_size: int,
    ) -> PlayerStatsListing:
        stats = await self.stats.fetch_many(
            player_id=player_id,
            page=page,
            page_size=page_size,
        )
        total_stats = await self.stats.fetch_count(player_id=player_id)

        return PlayerStatsListing(stats=stats, total_stats=total_stats)
