"""bancho.py's v2 apis for interacting with maps"""

from __future__ import annotations

import dataclasses
from typing import Annotated
from typing import Literal

from fastapi import APIRouter
from fastapi import Depends
from fastapi import status
from fastapi.param_functions import Query

from app.api import dependencies as api_dependencies
from app.api.v2.common import responses
from app.api.v2.common.parameters import GameModeParam
from app.api.v2.common.responses import Failure
from app.api.v2.common.responses import Success
from app.api.v2.models.maps import Map
from app.api.v2.models.maps import MapRating
from app.api.v2.models.scores import MapScore
from app.api.v2.models.scores import ScorePlayer
from app.constants.gamemodes import GameMode
from app.services.maps import BeatmapRatingService
from app.services.maps import MapsService
from app.services.scores import ScoresService

router = APIRouter()


@router.get("/maps")
async def get_maps(
    *,
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
    maps_service: Annotated[
        MapsService,
        Depends(api_dependencies.get_maps_service),
    ],
) -> Success[list[Map]] | Failure:
    listing = await maps_service.fetch_maps(
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

    response = [Map.model_validate(rec) for rec in listing.maps]

    return responses.success(
        content=response,
        meta={
            "total": listing.total_maps,
            "page": page,
            "page_size": page_size,
        },
    )


@router.get("/maps/{map_id}")
async def get_map(
    map_id: int,
    maps_service: Annotated[
        MapsService,
        Depends(api_dependencies.get_maps_service),
    ],
) -> Success[Map] | Failure:
    data = await maps_service.fetch_map(map_id)
    if data is None:
        return responses.failure(
            message="Map not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    response = Map.model_validate(data)
    return responses.success(response)


@router.get("/maps/{map_id}/rating")
async def get_map_rating(
    map_id: int,
    maps_service: Annotated[
        MapsService,
        Depends(api_dependencies.get_maps_service),
    ],
    beatmap_rating_service: Annotated[
        BeatmapRatingService,
        Depends(api_dependencies.get_beatmap_rating_service),
    ],
) -> Success[MapRating] | Failure:
    beatmap = await maps_service.fetch_map(map_id)
    if beatmap is None:
        return responses.failure(
            message="Map not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    stats = await beatmap_rating_service.fetch_map_rating_stats(beatmap.md5)
    response = MapRating(average=stats.average, count=stats.count)
    return responses.success(response)


@router.get("/maps/{map_id}/scores")
async def get_map_scores(
    map_id: int,
    *,
    scope: Literal["best", "recent"] = "best",
    mode: GameModeParam = Query(0),
    limit: int = Query(50, ge=1, le=100),
    maps_service: Annotated[
        MapsService,
        Depends(api_dependencies.get_maps_service),
    ],
    scores_service: Annotated[
        ScoresService,
        Depends(api_dependencies.get_scores_service),
    ],
) -> Success[list[MapScore]] | Failure:
    bmap = await maps_service.fetch_map(map_id)
    if bmap is None:
        return responses.failure(
            message="Map not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    scores = await scores_service.fetch_map_scores(
        map_md5=bmap.md5,
        mode=GameMode(mode),
        mods=None,
        strong_mods_equality=True,
        scope=scope,
        limit=limit,
    )

    response = [
        MapScore.model_validate(
            {
                **dataclasses.asdict(rec),
                "player": ScorePlayer(
                    id=rec.userid,
                    name=rec.player_name,
                    country=rec.player_country,
                    clan_id=rec.clan_id,
                    clan_name=rec.clan_name,
                    clan_tag=rec.clan_tag,
                ),
            },
        )
        for rec in scores
    ]

    return responses.success(
        content=response,
        meta={
            "total": len(response),
            "scope": scope,
            "mode": mode,
        },
    )
