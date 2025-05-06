from __future__ import annotations

from fastapi.param_functions import Depends
from fastapi.param_functions import Query
from fastapi.responses import Response
from fastapi.routing import APIRouter

from app.api.web.authentication import authenticate_player_session
from app.objects.player import Player

router = APIRouter()


@router.get("/osu-getfriends.php")
async def osuGetFriends(
    player: Player = Depends(authenticate_player_session(Query, "u", "h")),
) -> Response:
    return Response("\n".join(map(str, player.friends)).encode())
