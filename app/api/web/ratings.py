from __future__ import annotations

from fastapi.param_functions import Depends
from fastapi.param_functions import Query
from fastapi.responses import Response
from fastapi.routing import APIRouter

import app.state
from app.api.web.authentication import authenticate_player_session
from app.objects.beatmap import RankedStatus
from app.objects.player import Player
from app.repositories import ratings as ratings_repo

router = APIRouter()


@router.get("/osu-rate.php")
async def osuRate(
    player: Player = Depends(
        authenticate_player_session(Query, "u", "p", err=b"auth fail"),
    ),
    map_md5: str = Query(..., alias="c", min_length=32, max_length=32),
    rating: int | None = Query(None, alias="v", ge=1, le=10),
) -> Response:
    if rating is None:
        # check if we have the map in our cache;
        # if not, the map probably doesn't exist.
        if map_md5 not in app.state.cache.beatmap:
            return Response(b"no exist")

        cached = app.state.cache.beatmap[map_md5]

        # only allow rating on maps with a leaderboard.
        if cached.status < RankedStatus.Ranked:
            return Response(b"not ranked")

        # osu! client is checking whether we can rate the map or not.
        # the client hasn't rated the map, so simply
        # tell them that they can submit a rating.
        if not await ratings_repo.fetch_one(map_md5=map_md5, userid=player.id):
            return Response(b"ok")
    else:
        # the client is submitting a rating for the map.
        await ratings_repo.create(userid=player.id, map_md5=map_md5, rating=rating)

    map_ratings = await ratings_repo.fetch_many(map_md5=map_md5)
    ratings = [row["rating"] for row in map_ratings]

    # send back the average rating
    avg = sum(ratings) / len(ratings)
    return Response(f"alreadyvoted\n{avg}".encode())
