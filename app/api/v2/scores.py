"""bancho.py's v2 apis for interacting with scores"""

from __future__ import annotations

import dataclasses
from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import status
from fastapi.param_functions import Query

from app.api import dependencies as api_dependencies
from app.api.v2.common import responses
from app.api.v2.common.responses import Failure
from app.api.v2.common.responses import Success
from app.api.v2.models.scores import Score
from app.api.v2.models.scores import ScoreBeatmap
from app.api.v2.models.scores import ScoreDetail
from app.api.v2.models.scores import ScorePlayer
from app.services.scores import ScoresService

router = APIRouter()


@router.get("/scores")
async def get_all_scores(
    *,
    map_md5: str | None = None,
    mods: int | None = None,
    status: int | None = None,
    mode: int | None = None,
    user_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    scores_service: Annotated[
        ScoresService,
        Depends(api_dependencies.get_scores_service),
    ],
) -> Success[list[Score]] | Failure:
    listing = await scores_service.fetch_scores(
        map_md5=map_md5,
        mods=mods,
        status=status,
        mode=mode,
        user_id=user_id,
        page=page,
        page_size=page_size,
    )

    response = [Score.model_validate(rec) for rec in listing.scores]

    return responses.success(
        content=response,
        meta={
            "total": listing.total_scores,
            "page": page,
            "page_size": page_size,
        },
    )


@router.get("/scores/{score_id}")
async def get_score(
    score_id: int,
    scores_service: Annotated[
        ScoresService,
        Depends(api_dependencies.get_scores_service),
    ],
) -> Success[ScoreDetail] | Failure:
    data = await scores_service.fetch_score_with_context(score_id)
    if data is None:
        return responses.failure(
            message="Score not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    response = ScoreDetail.model_validate(
        {
            **dataclasses.asdict(data.score),
            "beatmap": ScoreBeatmap.model_validate(data.beatmap),
            "player": ScorePlayer(
                id=data.player.id,
                name=data.player.name,
                country=data.player.country,
                clan_id=data.player.clan_id or None,
                clan_name=data.clan.name if data.clan is not None else None,
                clan_tag=data.clan.tag if data.clan is not None else None,
            ),
        },
    )
    return responses.success(response)
