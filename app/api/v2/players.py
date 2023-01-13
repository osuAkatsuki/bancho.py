""" bancho.py's v2 apis for interacting with players """
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from fastapi import status
from fastapi.param_functions import Query

import app.state.sessions
from app.api.v2.common import responses
from app.api.v2.common.responses import Success
from app.api.v2.models.players import Player
from app.api.v2.models.players import PlayerStats
from app.api.v2.models.players import PlayerStatus
from app.repositories import players as players_repo
from app.repositories import stats as stats_repo

router = APIRouter()


@router.get("/players")
async def get_players(
    priv: Optional[int] = None,
    country: Optional[str] = None,
    clan_id: Optional[int] = None,
    clan_priv: Optional[int] = None,
    preferred_mode: Optional[int] = None,
    play_style: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> Success[list[Player]]:
    players = await players_repo.fetch_many(
        priv=priv,
        country=country,
        clan_id=clan_id,
        clan_priv=clan_priv,
        preferred_mode=preferred_mode,
        play_style=play_style,
        page=page,
        page_size=page_size,
    )
    total_players = await players_repo.fetch_count(
        priv=priv,
        country=country,
        clan_id=clan_id,
        clan_priv=clan_priv,
        preferred_mode=preferred_mode,
        play_style=play_style,
    )

    response = [Player.from_mapping(rec) for rec in players]

    return responses.success(
        content=response,
        meta={
            "total": total_players,
            "page": page,
            "page_size": page_size,
        },
    )


@router.get("/players/{player_id}")
async def get_player(player_id: int) -> Success[Player]:
    data = await players_repo.fetch_one(id=player_id)
    if data is None:
        return responses.failure(
            message="Player not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    response = Player.from_mapping(data)
    return responses.success(response)


@router.get("/players/{player_id}/status")
async def get_player_status(player_id: int) -> Success[PlayerStatus]:
    player = app.state.sessions.players.get(id=player_id)

    if not player:
        return responses.failure(
            message="Player status not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    response = PlayerStatus(
        login_time=int(player.login_time),
        action=int(player.status.action),
        info_text=player.status.info_text,
        mode=int(player.status.mode),
        mods=int(player.status.mods),
        beatmap_id=player.status.map_id,
    )
    return responses.success(response)


@router.get("/players/{player_id}/stats/{mode}")
async def get_player_mode_stats(player_id: int, mode: int) -> Success[PlayerStats]:
    data = await stats_repo.fetch_one(player_id, mode)
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
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> Success[list[PlayerStats]]:
    data = await stats_repo.fetch_many(
        player_id=player_id,
        page=page,
        page_size=page_size,
    )
    total_stats = await stats_repo.fetch_count(
        player_id=player_id,
    )

    response = [PlayerStats.from_mapping(rec) for rec in data]
    return responses.success(
        response,
        meta={
            "total": total_stats,
            "page": page,
            "page_size": page_size,
        },
    )
