"""bancho.py's v2 apis for interacting with overall server state"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends

from app.api import dependencies as api_dependencies
from app.api.v2.common import responses
from app.api.v2.common.responses import Failure
from app.api.v2.common.responses import Success
from app.api.v2.models.server import ServerStats
from app.services.players import PlayersService

router = APIRouter()


@router.get("/server/stats")
async def get_server_stats(
    players_service: Annotated[
        PlayersService,
        Depends(api_dependencies.get_players_service),
    ],
) -> Success[ServerStats] | Failure:
    response = ServerStats(
        online_players=players_service.fetch_online_player_count(),
        total_players=await players_service.fetch_total_player_count(),
    )
    return responses.success(response)
