""" bancho.py's v2 apis for interacting with players """

from __future__ import annotations

from fastapi import APIRouter
from fastapi import status
from fastapi.param_functions import Query

import app.state.sessions
from app.api.v2.common import responses
from app.api.v2.common.responses import Failure
from app.api.v2.common.responses import Success
from app.api.v2.models.players import Player
from app.api.v2.models.players import PlayerStats
from app.api.v2.models.players import PlayerStatus
from app.constants.level import get_level
from app.constants.level import get_level_precise
from app.repositories import stats as stats_repo
from app.repositories import users as users_repo

router = APIRouter()


@router.get("/players")
async def get_players(
    priv: int | None = None,
    country: str | None = None,
    clan_id: int | None = None,
    clan_priv: int | None = None,
    preferred_mode: int | None = None,
    play_style: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> Success[list[Player]] | Failure:
    players = await users_repo.fetch_many(
        priv=priv,
        country=country,
        clan_id=clan_id,
        clan_priv=clan_priv,
        preferred_mode=preferred_mode,
        play_style=play_style,
        page=page,
        page_size=page_size,
    )
    total_players = await users_repo.fetch_count(
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
async def get_player(player_id: int) -> Success[Player] | Failure:
    data = await users_repo.fetch_one(id=player_id)
    if data is None:
        return responses.failure(
            message="Player not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    response = Player.from_mapping(data)
    return responses.success(response)


@router.get("/players/{player_id}/status")
async def get_player_status(player_id: int) -> Success[PlayerStatus] | Failure:
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
async def get_player_mode_stats(
    player_id: int,
    mode: int,
) -> Success[PlayerStats] | Failure:
    data = await stats_repo.fetch_one(player_id, mode)
    if data is None:
        return responses.failure(
            message="Player stats not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    response = PlayerStats.from_mapping(data)

    # NOTE: kinda cursed, but that should do it
    response.level = get_level(int(data["tscore"]))
    response.level_progress = int(
        (get_level_precise(data["tscore"]) - get_level(data["tscore"])) * 100,
    )
    response.level_precise = get_level_precise(data["tscore"]);

    return responses.success(response)


@router.get("/players/{player_id}/stats")
async def get_player_stats(
    player_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> Success[list[PlayerStats]] | Failure:
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
