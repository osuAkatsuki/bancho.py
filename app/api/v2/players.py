""" api-v2: redefined bancho.py's developer api for interacting with players repository """
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/players/{player_id}")
async def get_player(player_id: int):
    return f"Hello! {player_id}"
