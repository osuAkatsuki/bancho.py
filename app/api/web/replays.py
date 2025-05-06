from __future__ import annotations

from pathlib import Path as SystemPath

from fastapi.param_functions import Depends
from fastapi.param_functions import Query
from fastapi.responses import FileResponse
from fastapi.responses import Response
from fastapi.routing import APIRouter

import app.state
from app.api.web.authentication import authenticate_player_session
from app.objects.player import Player
from app.objects.score import Score

REPLAYS_PATH = SystemPath.cwd() / ".data/osr"


router = APIRouter()


@router.get("/osu-getreplay.php")
async def getReplay(
    player: Player = Depends(authenticate_player_session(Query, "u", "h")),
    mode: int = Query(..., alias="m", ge=0, le=3),
    score_id: int = Query(..., alias="c", min=0, max=9_223_372_036_854_775_807),
) -> Response:
    score = await Score.from_sql(score_id)
    if not score:
        return Response(b"", status_code=404)

    file = REPLAYS_PATH / f"{score_id}.osr"
    if not file.exists():
        return Response(b"", status_code=404)

    # increment replay views for this score
    if score.player is not None and player.id != score.player.id:
        app.state.loop.create_task(score.increment_replay_views())  # type: ignore[unused-awaitable]

    return FileResponse(file)
