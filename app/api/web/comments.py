from __future__ import annotations

from typing import Literal

from fastapi.param_functions import Depends
from fastapi.param_functions import Form
from fastapi.responses import Response
from fastapi.routing import APIRouter

from app.api.web.authentication import authenticate_player_session
from app.constants.privileges import Privileges
from app.logging import log
from app.objects.player import Player
from app.repositories import comments as comments_repo

router = APIRouter()


@router.post("/osu-comment.php")
async def osuComment(
    player: Player = Depends(authenticate_player_session(Form, "u", "p")),
    map_id: int = Form(..., alias="b"),
    map_set_id: int = Form(..., alias="s"),
    score_id: int = Form(..., alias="r", ge=0, le=9_223_372_036_854_775_807),
    mode_vn: int = Form(..., alias="m", ge=0, le=3),
    action: Literal["get", "post"] = Form(..., alias="a"),
    # only sent for post
    target: Literal["song", "map", "replay"] | None = Form(None),
    colour: str | None = Form(None, alias="f", min_length=6, max_length=6),
    start_time: int | None = Form(None, alias="starttime"),
    comment: str | None = Form(None, min_length=1, max_length=80),
) -> Response:
    if action == "get":
        # client is requesting all comments
        comments = await comments_repo.fetch_all_relevant_to_replay(
            score_id=score_id,
            map_set_id=map_set_id,
            map_id=map_id,
        )

        ret: list[str] = []

        for cmt in comments:
            # note: this implementation does not support
            #       "player" or "creator" comment colours
            if cmt["priv"] & Privileges.NOMINATOR:
                fmt = "bat"
            elif cmt["priv"] & Privileges.DONATOR:
                fmt = "supporter"
            else:
                fmt = ""

            if cmt["colour"]:
                fmt += f'|{cmt["colour"]}'

            ret.append(
                "{time}\t{target_type}\t{fmt}\t{comment}".format(fmt=fmt, **cmt),
            )

        player.update_latest_activity_soon()
        return Response("\n".join(ret).encode())

    elif action == "post":
        # client is submitting a new comment

        # validate all required params are provided
        assert target is not None
        assert start_time is not None
        assert comment is not None

        # get the corresponding id from the request
        if target == "song":
            target_id = map_set_id
        elif target == "map":
            target_id = map_id
        else:  # target == "replay"
            target_id = score_id

        if colour and not player.priv & Privileges.DONATOR:
            # only supporters can use colours.
            colour = None

            log(
                f"User {player} attempted to use a coloured comment without "
                "supporter status. Submitting comment without a colour.",
            )

        # insert into sql
        await comments_repo.create(
            target_id=target_id,
            target_type=comments_repo.TargetType(target),
            userid=player.id,
            time=start_time,
            comment=comment,
            colour=colour,
        )

        player.update_latest_activity_soon()

    return Response(b"")  # empty resp is fine
