"""bancho.py's v2 apis for interacting with maps"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi import status
from fastapi.param_functions import Query

from app.api.v2.common import responses
from app.api.v2.common.responses import Failure
from app.api.v2.common.responses import Success
from app.api.v2.models.maps import Map
from app.repositories import maps as maps_repo

router = APIRouter()


@router.get("/maps")
async def get_maps(
    set_id: int | None = None,
    server: str | None = None,
    status: int | None = None,
    artist: str | None = None,
    creator: str | None = None,
    filename: str | None = None,
    mode: int | None = None,
    frozen: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> Success[list[Map]] | Failure:
    maps = await maps_repo.fetch_many(
        server=server,
        set_id=set_id,
        status=status,
        artist=artist,
        creator=creator,
        filename=filename,
        mode=mode,
        frozen=frozen,
        page=page,
        page_size=page_size,
    )
    total_maps = await maps_repo.fetch_count(
        server=server,
        set_id=set_id,
        status=status,
        artist=artist,
        creator=creator,
        filename=filename,
        mode=mode,
        frozen=frozen,
    )

    response = [Map.from_mapping(rec) for rec in maps]

    return responses.success(
        content=response,
        meta={
            "total": total_maps,
            "page": page,
            "page_size": page_size,
        },
    )


@router.get("/maps/{map_id}")
async def get_map(map_id: int) -> Success[Map] | Failure:
    data = await maps_repo.fetch_one(id=map_id)
    if data is None:
        return responses.failure(
            message="Map not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    response = Map.from_mapping(data)
    return responses.success(response)
