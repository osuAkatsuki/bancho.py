""" bancho.py's v2 apis for interacting with scores """
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from fastapi import status
from fastapi.param_functions import Query

from app.api.v2.common import responses
from app.api.v2.common.responses import Success
from app.api.v2.models.scores import Score
from app.repositories import scores as scores_repo

router = APIRouter()


@router.get("/scores")
async def get_all_scores(
    map_md5: Optional[str] = None,
    mods: Optional[int] = None,
    status: Optional[int] = None,
    mode: Optional[int] = None,
    user_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> Success[list[Score]]:
    scores = await scores_repo.fetch_many(
        map_md5=map_md5,
        mods=mods,
        status=status,
        mode=mode,
        user_id=user_id,
        page=page,
        page_size=page_size,
    )
    total_scores = await scores_repo.fetch_count(
        map_md5=map_md5,
        mods=mods,
        status=status,
        mode=mode,
        user_id=user_id,
    )

    response = [Score.from_mapping(rec) for rec in scores]

    return responses.success(
        content=response,
        meta={
            "total": total_scores,
            "page": page,
            "page_size": page_size,
        },
    )


@router.get("/scores/{score_id}")
async def get_score(score_id: int) -> Success[Score]:
    data = await scores_repo.fetch_one(id=score_id)
    if data is None:
        return responses.failure(
            message="Score not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    response = Score.from_mapping(data)
    return responses.success(response)
