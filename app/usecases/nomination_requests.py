from __future__ import annotations

from app import repositories
from app.objects.nomination_requests import NominationRequest
from app.objects.player import Player

## writes


async def create(player: Player, map_set_id: int) -> None:
    await repositories.favourite_beatmap_sets.create(player.id, map_set_id)


## reads


async def fetch_all() -> list[NominationRequest]:
    return await repositories.nomination_requests.fetch_all()
