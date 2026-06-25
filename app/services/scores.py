from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from typing import TypedDict

from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.repositories.scores import PublicMapScore
from app.repositories.scores import PublicMostPlayedMap
from app.repositories.scores import ReplayHeader
from app.repositories.scores import Score
from app.repositories.scores import ScoresRepository


class Beatmap(Protocol):
    @property
    def as_dict(self) -> dict[str, object]: ...


class BeatmapFetcher(Protocol):
    def __call__(self, md5: str, set_id: int = -1) -> Awaitable[Beatmap | None]: ...


class PlayerScoreWithBeatmap(TypedDict):
    id: int
    score: int
    pp: float
    acc: float
    max_combo: int
    mods: int
    n300: int
    n100: int
    n50: int
    nmiss: int
    ngeki: int
    nkatu: int
    grade: str
    status: int
    mode: int
    play_time: datetime
    time_elapsed: int
    perfect: int
    beatmap: dict[str, object] | None


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
        for row in await self.scores.fetch_public_player_scores(
            user_id=player_id,
            mode=int(mode),
            mods=int(mods) if mods is not None else None,
            strong_mods_equality=strong_mods_equality,
            scope=scope,
            limit=limit,
            include_loved=include_loved,
            include_failed=include_failed,
        ):
            beatmap = await self.fetch_beatmap(row["map_md5"])
            rows.append(
                {
                    "id": row["id"],
                    "score": row["score"],
                    "pp": row["pp"],
                    "acc": row["acc"],
                    "max_combo": row["max_combo"],
                    "mods": row["mods"],
                    "n300": row["n300"],
                    "n100": row["n100"],
                    "n50": row["n50"],
                    "nmiss": row["nmiss"],
                    "ngeki": row["ngeki"],
                    "nkatu": row["nkatu"],
                    "grade": row["grade"],
                    "status": row["status"],
                    "mode": row["mode"],
                    "play_time": row["play_time"],
                    "time_elapsed": row["time_elapsed"],
                    "perfect": row["perfect"],
                    "beatmap": beatmap.as_dict if beatmap else None,
                },
            )

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

    async def fetch_replay_header(self, score_id: int) -> ReplayHeader | None:
        return await self.scores.fetch_replay_header(score_id)
