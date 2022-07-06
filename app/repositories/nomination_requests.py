from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.objects.nomination_requests import NominationRequest
from app.state import services

## writes


async def create(player_id: int, beatmap_id: int) -> None:
    await services.database.execute(
        "INSERT INTO map_requests "
        "(map_id, player_id, datetime, active) "
        "VALUES (:map_id, :user_id, NOW(), 1)",
        {"map_id": beatmap_id, "user_id": player_id},
    )


## reads


async def fetch_all() -> list[NominationRequest]:
    rows = await services.database.fetch_all(
        "SELECT map_id, player_id, datetime FROM map_requests WHERE active = 1",
    )

    return [
        NominationRequest(
            player_id=row["player_id"],
            map_id=row["map_id"],
            created_at=row["datetime"],
            updated_at=None,  # TODO
        )
        for row in rows
    ]
