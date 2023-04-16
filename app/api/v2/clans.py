""" bancho.py's v2 apis for interacting with clans """
from __future__ import annotations

from fastapi import APIRouter
from fastapi import status
from fastapi.param_functions import Query

from app.api.v2.common import responses
from app.api.v2.common.responses import Success
from app.api.v2.models.clans import Clan
from app.repositories import clans as clans_repo

router = APIRouter()


@router.get("/clans")
async def get_clans(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> Success[list[Clan]]:
    clans = await clans_repo.fetch_many(
        page=page,
        page_size=page_size,
    )
    total_clans = await clans_repo.fetch_count()

    response = [Clan.from_mapping(rec) for rec in clans]
    return responses.success(
        content=response,
        meta={
            "total": total_clans,
            "page": page,
            "page_size": page_size,
        },
    )


@router.get("/clans/{clan_id}")
async def get_clan(clan_id: int) -> Success[Clan]:
    data = await clans_repo.fetch_one(id=clan_id)
    if data is None:
        return responses.failure(
            message="Clan not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    response = Clan.from_mapping(data)
    return responses.success(response)
