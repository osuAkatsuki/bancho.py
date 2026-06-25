"""bancho.py's v2 apis for interacting with clans"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import status
from fastapi.param_functions import Query

from app.api import dependencies as api_dependencies
from app.api.v2.common import responses
from app.api.v2.common.responses import Failure
from app.api.v2.common.responses import Success
from app.api.v2.models.clans import Clan
from app.services.clans import ClansService

router = APIRouter()


@router.get("/clans")
async def get_clans(
    *,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    clans_service: Annotated[
        ClansService,
        Depends(api_dependencies.get_clans_service),
    ],
) -> Success[list[Clan]] | Failure:
    listing = await clans_service.fetch_clans(page=page, page_size=page_size)

    response = [Clan.from_mapping(rec) for rec in listing.clans]
    return responses.success(
        content=response,
        meta={
            "total": listing.total_clans,
            "page": page,
            "page_size": page_size,
        },
    )


@router.get("/clans/{clan_id}")
async def get_clan(
    clan_id: int,
    clans_service: Annotated[
        ClansService,
        Depends(api_dependencies.get_clans_service),
    ],
) -> Success[Clan] | Failure:
    data = await clans_service.fetch_clan(clan_id)
    if data is None:
        return responses.failure(
            message="Clan not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    response = Clan.from_mapping(data)
    return responses.success(response)
