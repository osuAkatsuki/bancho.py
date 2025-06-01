from __future__ import annotations

from fastapi.param_functions import Depends
from fastapi.param_functions import Query
from fastapi.responses import Response
from fastapi.routing import APIRouter

from app.api.web.authentication import authenticate_player_session
from app.objects.player import Player
from app.repositories import favourites as favourites_repo

router = APIRouter()


@router.get("/osu-getfavourites.php")
async def osuGetFavourites(
    player: Player = Depends(authenticate_player_session(Query, "u", "h")),
) -> Response:
    favourites = await favourites_repo.fetch_all(userid=player.id)

    return Response(
        "\n".join([str(favourite["setid"]) for favourite in favourites]).encode(),
    )


@router.get("/osu-addfavourite.php")
async def osuAddFavourite(
    player: Player = Depends(authenticate_player_session(Query, "u", "h")),
    map_set_id: int = Query(..., alias="a"),
) -> Response:
    # check if they already have this favourited.
    if await favourites_repo.fetch_one(player.id, map_set_id):
        return Response(b"You've already favourited this beatmap!")

    # add favourite
    await favourites_repo.create(
        userid=player.id,
        setid=map_set_id,
    )

    return Response(b"Added favourite!")
