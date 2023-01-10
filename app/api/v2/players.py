""" api-v2: redefined bancho.py's developer api for interacting with players repository """
from __future__ import annotations

from typing import Union

from fastapi import APIRouter

from app.api.v2.models.players import Player
from app.api.v2.responses.error import failure
from app.api.v2.responses.success import Success
from app.api.v2.responses.success import success
from app.repositories import players as players_repo

router = APIRouter()


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
