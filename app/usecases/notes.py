from __future__ import annotations

from datetime import datetime
from typing import Any
from typing import Literal
from typing import Mapping
from typing import Optional
from typing import Sequence

from app import repositories

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
    return await repositories.notes.create(
        action,
        message,
        receiver_id,
        sender_id,
        created_at,
    )


## read


# TODO: filters when fetching?
async def fetch_notes_by_player_id(player_id: int) -> Sequence[Mapping[str, Any]]:
    """Retrieve the notes for a specific player by id."""
    return await repositories.notes.fetch_notes_by_player_id(player_id)


## update

## delete
