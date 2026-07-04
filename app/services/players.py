from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from typing import Protocol

from app.constants.privileges import Privileges
from app.objects.player import Player
from app.repositories.stats import Stat
from app.repositories.stats import StatsRepository
from app.repositories.users import SearchUser
from app.repositories.users import User
from app.repositories.users import UsersRepository
from app.services.player_leaderboards import ModeRanks
from app.services.player_leaderboards import PlayerLeaderboardsService


class OnlinePlayers(Protocol):
    @property
    def unrestricted(self) -> Collection[Player]: ...

    def get(
        self,
        token: str | None = None,
        id: int | None = None,
        name: str | None = None,
    ) -> Player | None: ...

    async def from_cache_or_sql(
        self,
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
class RankedStat:
    id: int
    mode: int
    tscore: int
    rscore: int
    pp: int
    plays: int
    playtime: int
    acc: float
    max_combo: int
    total_hits: int
    replay_views: int
    xh_count: int
    x_count: int
    sh_count: int
    s_count: int
    a_count: int
    # None = unranked for the mode
    rank: int | None
    country_rank: int | None


@dataclass(frozen=True)
class RankedStatsListing:
    stats: list[RankedStat]
    total_stats: int


def _ranked_stat(stat: Stat, ranks: ModeRanks) -> RankedStat:
    return RankedStat(
        id=stat.id,
        mode=stat.mode,
        tscore=stat.tscore,
        rscore=stat.rscore,
        pp=stat.pp,
        plays=stat.plays,
        playtime=stat.playtime,
        acc=stat.acc,
        max_combo=stat.max_combo,
        total_hits=stat.total_hits,
        replay_views=stat.replay_views,
        xh_count=stat.xh_count,
        x_count=stat.x_count,
        sh_count=stat.sh_count,
        s_count=stat.s_count,
        a_count=stat.a_count,
        rank=ranks.global_rank,
        country_rank=ranks.country_rank,
    )


@dataclass(frozen=True)
class PlayersService:
    users: UsersRepository
    stats: StatsRepository
    online_players: OnlinePlayers
    player_leaderboards: PlayerLeaderboardsService

    async def search_players(
        self,
        search: str | None,
        *,
        viewer: User | None,
    ) -> list[SearchUser]:
        """Search players by name. Staff see hidden (restricted or
        unverified) players; any signed-in player can find themselves."""
        viewer_is_staff = (
            viewer is not None and viewer.priv & Privileges.STAFF.value != 0
        )
        return await self.users.search_public(
            name=search,
            include_hidden=viewer_is_staff,
            always_visible_id=viewer.id if viewer is not None else None,
        )

    def fetch_online_player_count(self) -> int:
        # The bot is always online and not included in the public count.
        return len(self.online_players.unrestricted) - 1

    async def fetch_total_player_count(self) -> int:
        return await self.users.fetch_count()

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

    async def fetch_player_by_id_or_name(
        self,
        *,
        user_id: int | None,
        username: str | None,
    ) -> User | None:
        if user_id is not None:
            return await self.users.fetch_one(id=user_id)
        if username is not None:
            return await self.users.fetch_one(name=username)

        raise ValueError("Must provide either user_id or username.")

    def fetch_online_player(
        self,
        *,
        user_id: int | None,
        username: str | None,
    ) -> Player | None:
        if user_id is not None:
            return self.online_players.get(id=user_id)
        if username is not None:
            return self.online_players.get(name=username)

        raise ValueError("Must provide either user_id or username.")

    async def fetch_player_session(
        self,
        *,
        user_id: int | None,
        username: str | None,
    ) -> Player | None:
        if user_id is not None:
            return await self.online_players.from_cache_or_sql(id=user_id)
        if username is not None:
            return await self.online_players.from_cache_or_sql(name=username)

        raise ValueError("Must provide either user_id or username.")

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

    async def fetch_all_player_stats(self, player_id: int) -> list[Stat]:
        return await self.stats.fetch_many(player_id=player_id)

    async def fetch_player_mode_stats_with_ranks(
        self,
        *,
        player_id: int,
        mode: int,
        country: str,
    ) -> RankedStat | None:
        stat = await self.stats.fetch_one(player_id, mode)
        if stat is None:
            return None

        ranks = await self.player_leaderboards.fetch_player_mode_ranks(
            player_id=player_id,
            mode=mode,
            country=country,
        )
        return _ranked_stat(stat, ranks)

    async def fetch_player_stats_with_ranks(
        self,
        *,
        player_id: int,
        country: str,
        page: int,
        page_size: int,
    ) -> RankedStatsListing:
        listing = await self.fetch_player_stats(
            player_id=player_id,
            page=page,
            page_size=page_size,
        )

        ranked_stats = []
        for stat in listing.stats:
            ranks = await self.player_leaderboards.fetch_player_mode_ranks(
                player_id=player_id,
                mode=stat.mode,
                country=country,
            )
            ranked_stats.append(_ranked_stat(stat, ranks))

        return RankedStatsListing(
            stats=ranked_stats,
            total_stats=listing.total_stats,
        )
