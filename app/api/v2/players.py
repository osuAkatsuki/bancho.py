"""bancho.py's v2 apis for interacting with players"""

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
from app.api.v2.models.players import Player
from app.api.v2.models.players import PlayerStats
from app.api.v2.models.players import PlayerStatus
from app.services.players import PlayersService

router = APIRouter()


@router.get("/players")
async def get_players(
    *,
    priv: int | None = None,
    country: str | None = None,
    clan_id: int | None = None,
    clan_priv: int | None = None,
    preferred_mode: int | None = None,
    play_style: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    players_service: Annotated[
        PlayersService,
        Depends(api_dependencies.get_players_service),
    ],
) -> Success[list[Player]] | Failure:
    listing = await players_service.fetch_players(
        priv=priv,
        country=country,
        clan_id=clan_id,
        clan_priv=clan_priv,
        preferred_mode=preferred_mode,
        play_style=play_style,
        page=page,
        page_size=page_size,
    )

    response = [Player.from_mapping(rec) for rec in listing.players]

    return responses.success(
        content=response,
        meta={
            "total": listing.total_players,
            "page": page,
            "page_size": page_size,
        },
    )


@router.get("/players/{player_id}")
async def get_player(
    player_id: int,
    players_service: Annotated[
        PlayersService,
        Depends(api_dependencies.get_players_service),
    ],
) -> Success[Player] | Failure:
    data = await players_service.fetch_player(player_id)
    if data is None:
        return responses.failure(
            message="Player not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    response = Player.from_mapping(data)
    return responses.success(response)


@router.get("/players/{player_id}/status")
async def get_player_status(
    player_id: int,
    players_service: Annotated[
        PlayersService,
        Depends(api_dependencies.get_players_service),
    ],
) -> Success[PlayerStatus] | Failure:
    status_data = players_service.fetch_player_status(player_id)
    if status_data is None:
        return responses.failure(
            message="Player status not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    response = PlayerStatus(
        login_time=status_data.login_time,
        action=status_data.action,
        info_text=status_data.info_text,
        mode=status_data.mode,
        mods=status_data.mods,
        beatmap_id=status_data.beatmap_id,
    )
    return responses.success(response)


@router.get("/players/{player_id}/stats/{mode}")
async def get_player_mode_stats(
    player_id: int,
    mode: int,
    players_service: Annotated[
        PlayersService,
        Depends(api_dependencies.get_players_service),
    ],
) -> Success[PlayerStats] | Failure:
    data = await players_service.fetch_player_mode_stats(
        player_id=player_id,
        mode=mode,
    )
    if data is None:
        return responses.failure(
            message="Player stats not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    response = PlayerStats.from_mapping(data)
    return responses.success(response)


@router.get("/players/{player_id}/stats")
async def get_player_stats(
    player_id: int,
    *,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    players_service: Annotated[
        PlayersService,
        Depends(api_dependencies.get_players_service),
    ],
) -> Success[list[PlayerStats]] | Failure:
    listing = await players_service.fetch_player_stats(
        player_id=player_id,
        page=page,
        page_size=page_size,
    )

    response = [PlayerStats.from_mapping(rec) for rec in listing.stats]
    return responses.success(
        response,
        meta={
            "total": listing.total_stats,
            "page": page,
            "page_size": page_size,
        },
    )
