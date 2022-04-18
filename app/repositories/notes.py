from __future__ import annotations

from datetime import datetime
from typing import Any
from typing import Literal
from typing import Mapping
from typing import Optional
from typing import Sequence

import app.state

### TODO: fully refactor notes to be stored in JSON format


## create


async def create(
    action: Literal["note", "silence", "restrict", "unrestrict"],
    message: str,
    receiver_id: int,
    sender_id: int,
    created_at: Optional[datetime] = None,
) -> None:
    """Add a note to a specific player by name."""
    await app.state.services.database.execute(
        "INSERT INTO logs (`from`, `to`, `action`, `msg`, `time`) "
        "VALUES (:from, :to, :action, :msg, :time)",
        {
            # TODO: rename these to `sender_id` and `receiver_id` in db
            "from": sender_id,
            "to": receiver_id,
            "action": action,
            "msg": message,  # TODO: fix inconsistency
            "time": created_at or datetime.now(),  # TODO: fix inconsistency
        },
    )


## read


# TODO: filters when fetching?
async def fetch_notes_by_player_id(player_id: int) -> Sequence[Mapping[str, Any]]:
    """Retrieve the notes for a specific player by id."""
    return await app.state.services.database.fetch_all(
        "SELECT `action`, `msg`, `time`, `from` "
        "FROM `logs` WHERE `to` = :to "
        "AND UNIX_TIMESTAMP(`time`) >= UNIX_TIMESTAMP(NOW()) - :seconds "
        "ORDER BY `time` ASC",
        {"to": player_id},
    )


## notes cannot be updated or deleted
