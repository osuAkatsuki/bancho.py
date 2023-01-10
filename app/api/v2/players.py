""" api-v2: redefined bancho.py's developer api for interacting with players repository """
from __future__ import annotations

from typing import List
from typing import Optional
from typing import Union

from fastapi import APIRouter
from fastapi.param_functions import Query

from app.api.v2.models.players import Player
from app.api.v2.models.players import Players
from app.api.v2.responses.error import failure
from app.api.v2.responses.success import Success
from app.api.v2.responses.success import success
from app.repositories import players as players_repo

router = APIRouter()


@router.get("/players", response_model=Success[Players])
async def get_players(
    page: Optional[int] = Query(1, ge=1),
    page_size: Optional[int] = Query(50, ge=50, le=100),
):
    players = await players_repo.fetch_many(page=page, page_size=page_size)

    if len(players) < 1:
        return failure("Reached the pages limit.")

    players_count = await players_repo.fetch_count()

    response = Players(
        players=[Player.from_mapping(x) for x in players],
        max_pages=players_count / page_size + 1,
        current_page=page,
    )
    return success(response)


@router.get("/players/{player}", response_model=Success[Player])
async def get_player(player: Union[int, str]):
    if isinstance(player, int):
        player_info = await players_repo.fetch_one(id=player)
    else:
        player_info = await players_repo.fetch_one(name=player)

    if player_info is None:
        return failure("Player not found.", 404)

    response = Player.from_mapping(player_info)
    return success(response)
