from __future__ import annotations

from app import repositories
from app.objects.player import Player


## reads


async def exists(player: Player, map_set_id: int) -> bool:
    return await repositories.favourite_beatmap_sets.exists(player.id, map_set_id)


async def fetch_set_ids(player: Player) -> list[int]:
    return await repositories.favourite_beatmap_sets.fetch_set_ids(player.id)


## writes


async def create(player: Player, map_set_id: int) -> None:
    await repositories.favourite_beatmap_sets.create(player.id, map_set_id)
