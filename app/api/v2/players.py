"""bancho.py's v2 apis for interacting with players"""

from __future__ import annotations

import dataclasses
from typing import Annotated
from typing import Literal

from fastapi import APIRouter
from fastapi import Depends
from fastapi import status
from fastapi.datastructures import UploadFile
from fastapi.param_functions import File
from fastapi.param_functions import Query

from app.api import dependencies as api_dependencies
from app.api.v2.common import responses
from app.api.v2.common.parameters import GameModeParam
from app.api.v2.common.parameters import SessionCookie
from app.api.v2.common.responses import Failure
from app.api.v2.common.responses import Success
from app.api.v2.models.maps import MostPlayedMap
from app.api.v2.models.players import Player
from app.api.v2.models.players import PlayerStats
from app.api.v2.models.players import PlayerStatus
from app.api.v2.models.players import SearchPlayer
from app.api.v2.models.scores import PlayerScore
from app.api.v2.models.scores import ScoreBeatmap
from app.constants.gamemodes import GameMode
from app.services.avatars import MAX_AVATAR_SIZE_BYTES
from app.services.avatars import AvatarsService
from app.services.avatars import AvatarUploadResultCode
from app.services.players import PlayersService
from app.services.scores import ScoresService
from app.services.web_sessions import WebSessionsService

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

    response = [Player.model_validate(rec) for rec in listing.players]

    return responses.success(
        content=response,
        meta={
            "total": listing.total_players,
            "page": page,
            "page_size": page_size,
        },
    )


@router.get("/players/search")
async def search_players(
    *,
    query: str = Query(..., alias="q", min_length=2, max_length=32),
    players_service: Annotated[
        PlayersService,
        Depends(api_dependencies.get_players_service),
    ],
) -> Success[list[SearchPlayer]] | Failure:
    players = await players_service.search_public_players(query)

    response = [SearchPlayer.model_validate(rec) for rec in players]
    return responses.success(
        content=response,
        meta={"total": len(response)},
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

    response = Player.model_validate(data)
    return responses.success(response)


@router.put("/players/{player_id}/avatar")
async def update_player_avatar(
    player_id: int,
    avatar_file: UploadFile = File(...),
    session_token: SessionCookie = None,
    *,
    web_sessions_service: Annotated[
        WebSessionsService,
        Depends(api_dependencies.get_web_sessions_service),
    ],
    avatars_service: Annotated[
        AvatarsService,
        Depends(api_dependencies.get_avatars_service),
    ],
) -> Success[None] | Failure:
    if session_token is None:
        return responses.failure(
            message="Authentication required.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    user = await web_sessions_service.fetch_session_user(session_token)
    if user is None:
        return responses.failure(
            message="Invalid or expired session.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if user.id != player_id:
        return responses.failure(
            message="You may only update your own avatar.",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    result = await avatars_service.upload_avatar(
        user_id=user.id,
        avatar_data=await avatar_file.read(),
    )
    if result is AvatarUploadResultCode.FILE_TOO_LARGE:
        max_mb = MAX_AVATAR_SIZE_BYTES // (1024 * 1024)
        return responses.failure(
            message=f"Avatar file too large (max {max_mb}MB).",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if result is AvatarUploadResultCode.INVALID_FILE_TYPE:
        return responses.failure(
            message="Avatars must be png or jpeg images.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return responses.success(None)


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
    player = await players_service.fetch_player(player_id)
    if player is None:
        return responses.failure(
            message="Player not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    data = await players_service.fetch_player_mode_stats_with_ranks(
        player_id=player_id,
        mode=mode,
        country=player.country,
    )
    if data is None:
        return responses.failure(
            message="Player stats not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    response = PlayerStats.model_validate(data)
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
    player = await players_service.fetch_player(player_id)
    if player is None:
        return responses.failure(
            message="Player not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    listing = await players_service.fetch_player_stats_with_ranks(
        player_id=player_id,
        country=player.country,
        page=page,
        page_size=page_size,
    )

    response = [PlayerStats.model_validate(rec) for rec in listing.stats]

    return responses.success(
        response,
        meta={
            "total": listing.total_stats,
            "page": page,
            "page_size": page_size,
        },
    )


@router.get("/players/{player_id}/scores")
async def get_player_scores(
    player_id: int,
    *,
    scope: Literal["best", "recent"] = "best",
    mode: GameModeParam = Query(0),
    limit: int = Query(25, ge=1, le=100),
    include_loved: bool = False,
    include_failed: bool = True,
    players_service: Annotated[
        PlayersService,
        Depends(api_dependencies.get_players_service),
    ],
    scores_service: Annotated[
        ScoresService,
        Depends(api_dependencies.get_scores_service),
    ],
) -> Success[list[PlayerScore]] | Failure:
    player = await players_service.fetch_player(player_id)
    if player is None:
        return responses.failure(
            message="Player not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    scores = await scores_service.fetch_player_scores(
        player_id=player_id,
        mode=GameMode(mode),
        mods=None,
        strong_mods_equality=True,
        scope=scope,
        limit=limit,
        include_loved=include_loved,
        include_failed=include_failed,
    )

    response = [
        PlayerScore.model_validate(
            {
                **dataclasses.asdict(row.score),
                "beatmap": (
                    ScoreBeatmap.model_validate(row.beatmap)
                    if row.beatmap is not None
                    else None
                ),
            },
        )
        for row in scores
    ]

    return responses.success(
        content=response,
        meta={
            "total": len(response),
            "scope": scope,
            "mode": mode,
        },
    )


@router.get("/players/{player_id}/most_played")
async def get_player_most_played(
    player_id: int,
    *,
    mode: GameModeParam = Query(0),
    limit: int = Query(25, ge=1, le=100),
    players_service: Annotated[
        PlayersService,
        Depends(api_dependencies.get_players_service),
    ],
    scores_service: Annotated[
        ScoresService,
        Depends(api_dependencies.get_scores_service),
    ],
) -> Success[list[MostPlayedMap]] | Failure:
    player = await players_service.fetch_player(player_id)
    if player is None:
        return responses.failure(
            message="Player not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    maps = await scores_service.fetch_player_most_played(
        player_id=player_id,
        mode=GameMode(mode),
        limit=limit,
    )

    response = [MostPlayedMap.model_validate(rec) for rec in maps]
    return responses.success(
        content=response,
        meta={
            "total": len(response),
            "mode": mode,
        },
    )
