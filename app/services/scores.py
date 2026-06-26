from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Protocol

from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.objects.beatmap import Beatmap
from app.repositories.scores import MapScoreListingRow
from app.repositories.scores import MostPlayedMapRow
from app.repositories.scores import PlayerScoreListingRow
from app.repositories.scores import ReplayHeader
from app.repositories.scores import Score
from app.repositories.scores import ScoresRepository


class BeatmapFetcher(Protocol):
    def __call__(self, md5: str, set_id: int = -1) -> Awaitable[Beatmap | None]: ...


@dataclass(frozen=True)
class PlayerScoreWithBeatmap:
    score: PlayerScoreListingRow
    beatmap: Beatmap | None


@dataclass(frozen=True)
class ScoresListing:
    scores: list[Score]
    total_scores: int


@dataclass(frozen=True)
class ScoresService:
    scores: ScoresRepository
    fetch_beatmap: BeatmapFetcher

    async def fetch_scores(
        self,
        *,
        map_md5: str | None,
        mods: int | None,
        status: int | None,
        mode: int | None,
        user_id: int | None,
        page: int,
        page_size: int,
    ) -> ScoresListing:
        scores = await self.scores.fetch_many(
            map_md5=map_md5,
            mods=mods,
            status=status,
            mode=mode,
            user_id=user_id,
            page=page,
            page_size=page_size,
        )
        total_scores = await self.scores.fetch_count(
            map_md5=map_md5,
            mods=mods,
            status=status,
            mode=mode,
            user_id=user_id,
        )

        return ScoresListing(scores=scores, total_scores=total_scores)

    async def fetch_score(self, score_id: int) -> Score | None:
        return await self.scores.fetch_one(id=score_id)

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
    ) -> list[PlayerScoreWithBeatmap]:
        rows: list[PlayerScoreWithBeatmap] = []
        for row in await self.scores.fetch_player_score_listing_rows(
            user_id=player_id,
            mode=int(mode),
            mods=int(mods) if mods is not None else None,
            strong_mods_equality=strong_mods_equality,
            scope=scope,
            limit=limit,
            include_loved=include_loved,
            include_failed=include_failed,
        ):
            beatmap = await self.fetch_beatmap(row.map_md5)
            rows.append(
                PlayerScoreWithBeatmap(
                    score=row,
                    beatmap=beatmap,
                ),
            )

        return rows

    async def fetch_player_most_played(
        self,
        *,
        player_id: int,
        mode: GameMode,
        limit: int,
    ) -> list[MostPlayedMapRow]:
        return await self.scores.fetch_most_played_map_rows(
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
    ) -> list[MapScoreListingRow]:
        return await self.scores.fetch_map_score_listing_rows(
            map_md5=map_md5,
            mode=int(mode),
            mods=int(mods) if mods is not None else None,
            strong_mods_equality=strong_mods_equality,
            scope=scope,
            limit=limit,
        )

    async def fetch_replay_header(self, score_id: int) -> ReplayHeader | None:
        return await self.scores.fetch_replay_header(score_id)
