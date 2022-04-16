from __future__ import annotations

from typing import Any
from typing import Mapping
from typing import Optional
from typing import TYPE_CHECKING

import app.state.services

if TYPE_CHECKING:
    from app.objects.player import Player
# create


async def create(
    player: Player,
    target_type: str,
    target_id: int,
    colour: Optional[str],
    comment: str,
    start_time: int,
) -> None:
    await app.state.services.database.execute(
        "INSERT INTO comments "
        "(target_id, target_type, userid, time, comment, colour) "
        "VALUES (:target_id, :target_type, :userid, :time, :comment, :colour)",
        {
            "target_id": target_id,
            "target_type": target_type,
            "userid": player.id,
            "time": start_time,
            "comment": comment,
            "colour": colour,
        },
    )


# read


async def fetch_all(
    score_id: int,
    map_set_id: int,
    map_id: int,
) -> list[Mapping[str, Any]]:
    return await app.state.services.database.fetch_all(
        "SELECT c.time, c.target_type, c.colour, "
        "c.comment, u.priv FROM comments c "
        "INNER JOIN users u ON u.id = c.userid "
        "WHERE (c.target_type = 'replay' AND c.target_id = :score_id) "
        "OR (c.target_type = 'song' AND c.target_id = :set_id) "
        "OR (c.target_type = 'map' AND c.target_id = :map_id) ",
        {
            "score_id": score_id,
            "set_id": map_set_id,
            "map_id": map_id,
        },
    )


# update

# delete
