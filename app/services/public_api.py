from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.objects.beatmap import Beatmap
from app.repositories.clans import Clan
from app.repositories.clans import ClansRepository
from app.repositories.scores import PublicMapScore
from app.repositories.scores import PublicMostPlayedMap
from app.repositories.scores import PublicPlayerScore
from app.repositories.scores import ReplayHeader
from app.repositories.scores import Score
from app.repositories.scores import ScoresRepository
from app.repositories.stats import PublicLeaderboardRow
from app.repositories.stats import Stat
from app.repositories.stats import StatsRepository
from app.repositories.tourney_pool_maps import TourneyPoolMap
from app.repositories.tourney_pool_maps import TourneyPoolMapsRepository
from app.repositories.tourney_pools import TourneyPool
from app.repositories.tourney_pools import TourneyPoolsRepository
from app.repositories.users import SearchUser
from app.repositories.users import User
from app.repositories.users import UsersRepository


@dataclass(frozen=True)
class PublicApiService:
    users: UsersRepository
    stats: StatsRepository
    clans: ClansRepository
    scores: ScoresRepository
    tourney_pools: TourneyPoolsRepository
    tourney_pool_maps: TourneyPoolMapsRepository

    async def search_players(self, search: str | None) -> list[SearchUser]:
        return await self.users.search_public(name=search)

    async def fetch_total_player_count(self) -> int:
        return await self.users.fetch_count()

    async def fetch_player(
        self,
        *,
        user_id: int | None,
        username: str | None,
    ) -> User | None:
        if username is not None:
            return await self.users.fetch_one(name=username)
        if user_id is not None:
            return await self.users.fetch_one(id=user_id)

        raise ValueError("Must provide either user_id or username.")

    async def fetch_player_stats(self, player_id: int) -> list[Stat]:
        return await self.stats.fetch_many(player_id=player_id)

    async def fetch_player_scores(
        self,
        *,
        player_id: int,
        mode: GameMode,
        mods: Mods | None,
        strong_mods_equality: bool,
        scope: str,
        limit: int,
        include_loved: bool,
        include_failed: bool,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = [
            dict(row)
            for row in await self.scores.fetch_public_player_scores(
                user_id=player_id,
                mode=int(mode),
                mods=int(mods) if mods is not None else None,
                strong_mods_equality=strong_mods_equality,
                scope=scope,
                limit=limit,
                include_loved=include_loved,
                include_failed=include_failed,
            )
        ]

        for row in rows:
            bmap = await Beatmap.from_md5(row.pop("map_md5"))
            row["beatmap"] = bmap.as_dict if bmap else None

        return rows

    async def fetch_player_most_played(
        self,
        *,
        player_id: int,
        mode: GameMode,
        limit: int,
    ) -> list[PublicMostPlayedMap]:
        return await self.scores.fetch_public_player_most_played_maps(
            user_id=player_id,
            mode=int(mode),
            limit=limit,
        )

    async def fetch_map_scores(
        self,
        *,
        map_md5: str,
        mode: GameMode,
        mods: Mods | None,
        strong_mods_equality: bool,
        scope: str,
        limit: int,
    ) -> list[PublicMapScore]:
        return await self.scores.fetch_public_map_scores(
            map_md5=map_md5,
            mode=int(mode),
            mods=int(mods) if mods is not None else None,
            strong_mods_equality=strong_mods_equality,
            scope=scope,
            limit=limit,
        )

    async def fetch_score(self, score_id: int) -> Score | None:
        return await self.scores.fetch_one(score_id)

    async def fetch_replay_header(self, score_id: int) -> ReplayHeader | None:
        return await self.scores.fetch_replay_header(score_id)

    async def fetch_global_leaderboard(
        self,
        *,
        sort: str,
        mode: GameMode,
        limit: int,
        offset: int,
        country: str | None,
    ) -> list[PublicLeaderboardRow]:
        return await self.stats.fetch_public_leaderboard(
            sort=sort,
            mode=int(mode),
            limit=limit,
            offset=offset,
            country=country,
        )

    async def fetch_clan(self, clan_id: int) -> Clan | None:
        return await self.clans.fetch_one(id=clan_id)

    async def fetch_clan_members(self, clan_id: int) -> list[User]:
        return await self.users.fetch_many(clan_id=clan_id)

    async def fetch_tourney_pool(self, pool_id: int) -> TourneyPool | None:
        return await self.tourney_pools.fetch_by_id(id=pool_id)

    async def fetch_tourney_pool_maps(
        self,
        pool_id: int,
    ) -> list[TourneyPoolMap]:
        return await self.tourney_pool_maps.fetch_many(pool_id=pool_id)
