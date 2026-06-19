from __future__ import annotations

from urllib.parse import unquote

from fastapi.param_functions import Depends
from fastapi.param_functions import Query
from fastapi.responses import Response
from fastapi.routing import APIRouter

import app.state
from app.api.web.authentication import authenticate_player_session
from app.logging import Ansi
from app.logging import log
from app.objects.player import Player
from app.repositories import mail as mail_repo

router = APIRouter()


@router.get("/osu-markasread.php")
async def osuMarkAsRead(
    player: Player = Depends(authenticate_player_session(Query, "u", "h")),
    channel: str = Query(..., min_length=0, max_length=32),
) -> Response:
    target_name = unquote(channel)  # TODO: unquote needed?
    if not target_name:
        log(
            f"User {player} attempted to mark a channel as read without a target.",
            Ansi.LYELLOW,
        )
        return Response(b"")  # no channel specified

    target = await app.state.sessions.players.from_cache_or_sql(name=target_name)
    if target:
        # mark any unread mail from this user as read.
        await mail_repo.mark_conversation_as_read(
            to_id=player.id,
            from_id=target.id,
        )

    return Response(b"")
