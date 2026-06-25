from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.adapters.database import Database
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.objects.beatmap import Beatmap
from app.repositories.clans import Clan
from app.repositories.clans import ClansRepository
from app.repositories.scores import Score
from app.repositories.scores import ScoresRepository
from app.repositories.stats import Stat
from app.repositories.stats import StatsRepository
from app.repositories.tourney_pool_maps import TourneyPoolMap
from app.repositories.tourney_pool_maps import TourneyPoolMapsRepository
from app.repositories.tourney_pools import TourneyPool
from app.repositories.tourney_pools import TourneyPoolsRepository
from app.repositories.users import User
from app.repositories.users import UsersRepository


@dataclass(frozen=True)
class PublicApiService:
    database: Database
    users: UsersRepository
    stats: StatsRepository
    clans: ClansRepository
    scores: ScoresRepository
    tourney_pools: TourneyPoolsRepository
    tourney_pool_maps: TourneyPoolMapsRepository

    async def search_players(self, search: str | None) -> list[dict[str, Any]]:
        rows = await self.database.fetch_all(
            "SELECT id, name "
            "FROM users "
            "WHERE name LIKE COALESCE(:name, name) "
            "AND priv & 3 = 3 "
            "ORDER BY id ASC",
            {"name": f"%{search}%" if search is not None else None},
        )
        return [dict(row) for row in rows]

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
        query = [
            "SELECT t.id, t.map_md5, t.score, t.pp, t.acc, t.max_combo, "
            "t.mods, t.n300, t.n100, t.n50, t.nmiss, t.ngeki, t.nkatu, t.grade, "
            "t.status, t.mode, t.play_time, t.time_elapsed, t.perfect "
            "FROM scores t "
            "INNER JOIN maps b ON t.map_md5 = b.md5 "
            "WHERE t.userid = :user_id AND t.mode = :mode",
        ]

        params: dict[str, object] = {
            "user_id": player_id,
            "mode": mode,
        }

        if mods is not None:
            if strong_mods_equality:
                query.append("AND t.mods & :mods = :mods")
            else:
                query.append("AND t.mods & :mods != 0")

            params["mods"] = mods

        if scope == "best":
            allowed_statuses = [2, 3]

            if include_loved:
                allowed_statuses.append(5)

            query.append("AND t.status = 2 AND b.status IN :statuses")
            params["statuses"] = allowed_statuses
            sort = "t.pp"
        else:
            if not include_failed:
                query.append("AND t.status != 0")

            sort = "t.play_time"

        query.append(f"ORDER BY {sort} DESC LIMIT :limit")
        params["limit"] = limit

        rows = [
            dict(row) for row in await self.database.fetch_all(" ".join(query), params)
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
    ) -> list[dict[str, Any]]:
        rows = await self.database.fetch_all(
            "SELECT m.md5, m.id, m.set_id, m.status, "
            "m.artist, m.title, m.version, m.creator, COUNT(*) plays "
            "FROM scores s "
            "INNER JOIN maps m ON m.md5 = s.map_md5 "
            "WHERE s.userid = :user_id "
            "AND s.mode = :mode "
            "GROUP BY s.map_md5 "
            "ORDER BY plays DESC "
            "LIMIT :limit",
            {"user_id": player_id, "mode": mode, "limit": limit},
        )
        return [dict(row) for row in rows]

    async def fetch_map_scores(
        self,
        *,
        map_md5: str,
        mode: GameMode,
        mods: Mods | None,
        strong_mods_equality: bool,
        scope: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        query = [
            "SELECT s.map_md5, s.score, s.pp, s.acc, s.max_combo, s.mods, "
            "s.n300, s.n100, s.n50, s.nmiss, s.ngeki, s.nkatu, s.grade, s.status, "
            "s.mode, s.play_time, s.time_elapsed, s.userid, s.perfect, "
            "u.name player_name, u.country player_country, "
            "c.id clan_id, c.name clan_name, c.tag clan_tag "
            "FROM scores s "
            "INNER JOIN users u ON u.id = s.userid "
            "LEFT JOIN clans c ON c.id = u.clan_id "
            "WHERE s.map_md5 = :map_md5 "
            "AND s.mode = :mode "
            "AND s.status = 2 "
            "AND u.priv & 1",
        ]
        params: dict[str, object] = {
            "map_md5": map_md5,
            "mode": mode,
        }

        if mods is not None:
            if strong_mods_equality:
                query.append("AND mods & :mods = :mods")
            else:
                query.append("AND mods & :mods != 0")

            params["mods"] = mods

        # Unlike /get_player_scores, we sort by score or pp depending on the
        # mode played, since we want to replicate leaderboards.
        if scope == "best":
            sort = "pp" if mode >= GameMode.RELAX_OSU else "score"
        else:
            sort = "play_time"

        query.append(f"ORDER BY {sort} DESC LIMIT :limit")
        params["limit"] = limit

        rows = await self.database.fetch_all(" ".join(query), params)
        return [dict(row) for row in rows]

    async def fetch_score(self, score_id: int) -> Score | None:
        return await self.scores.fetch_one(score_id)

    async def fetch_replay_header(self, score_id: int) -> Mapping[str, Any] | None:
        return await self.database.fetch_one(
            "SELECT u.name username, m.md5 map_md5, "
            "m.artist, m.title, m.version, "
            "s.mode, s.n300, s.n100, s.n50, s.ngeki, "
            "s.nkatu, s.nmiss, s.score, s.max_combo, "
            "s.perfect, s.mods, s.play_time "
            "FROM scores s "
            "INNER JOIN users u ON u.id = s.userid "
            "INNER JOIN maps m ON m.md5 = s.map_md5 "
            "WHERE s.id = :score_id",
            {"score_id": score_id},
        )

    async def fetch_global_leaderboard(
        self,
        *,
        sort: str,
        mode: GameMode,
        limit: int,
        offset: int,
        country: str | None,
    ) -> list[dict[str, Any]]:
        query_conditions = ["s.mode = :mode", "u.priv & 1", f"s.{sort} > 0"]
        query_parameters: dict[str, object] = {"mode": mode}

        if country is not None:
            query_conditions.append("u.country = :country")
            query_parameters["country"] = country

        rows = await self.database.fetch_all(
            "SELECT u.id as player_id, u.name, u.country, s.tscore, s.rscore, "
            "s.pp, s.plays, s.playtime, s.acc, s.max_combo, "
            "s.xh_count, s.x_count, s.sh_count, s.s_count, s.a_count, "
            "c.id as clan_id, c.name as clan_name, c.tag as clan_tag "
            "FROM stats s "
            "LEFT JOIN users u USING (id) "
            "LEFT JOIN clans c ON u.clan_id = c.id "
            f"WHERE {' AND '.join(query_conditions)} "
            f"ORDER BY s.{sort} DESC LIMIT :offset, :limit",
            query_parameters | {"offset": offset, "limit": limit},
        )
        return [dict(row) for row in rows]

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
