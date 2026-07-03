"""bancho.py's v2 apis for interacting with leaderboards"""

from __future__ import annotations

from typing import Annotated
from typing import Literal

from fastapi import APIRouter
from fastapi import Depends
from fastapi import status
from fastapi.param_functions import Path
from fastapi.param_functions import Query

from app.api import dependencies as api_dependencies
from app.api.v2.common import responses
from app.api.v2.common.responses import Failure
from app.api.v2.common.responses import Success
from app.api.v2.models.leaderboards import LeaderboardEntry
from app.constants.gamemodes import GameMode
from app.services.players import PlayersService

router = APIRouter()


@router.get("/leaderboards/{mode}")
async def get_leaderboard(
    mode: Annotated[int, Path(ge=0, le=11)],
    *,
    sort: Literal["pp", "rscore", "tscore", "acc", "plays", "playtime"] = "pp",
    country: str | None = Query(None, min_length=2, max_length=2),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    players_service: Annotated[
        PlayersService,
        Depends(api_dependencies.get_players_service),
    ],
) -> Success[list[LeaderboardEntry]] | Failure:
    if mode not in GameMode.valid_gamemodes():
        return responses.failure(
            message="Invalid gamemode.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    offset = (page - 1) * page_size
    leaderboard = await players_service.fetch_global_leaderboard(
        sort=sort,
        mode=GameMode(mode),
        limit=page_size,
        offset=offset,
        country=country,
    )

    response = [
        LeaderboardEntry.model_validate(rec).model_copy(
            update={"rank": offset + idx + 1},
        )
        for idx, rec in enumerate(leaderboard)
    ]

    return responses.success(
        content=response,
        meta={
            "page": page,
            "page_size": page_size,
        },
    )
