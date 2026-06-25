from __future__ import annotations

from dataclasses import dataclass

from app.repositories.scores import Score
from app.repositories.scores import ScoresRepository


@dataclass(frozen=True)
class ScoresListing:
    scores: list[Score]
    total_scores: int


@dataclass(frozen=True)
class ScoresService:
    scores: ScoresRepository

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
