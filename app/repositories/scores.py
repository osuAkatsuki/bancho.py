from __future__ import annotations

from typing import Optional

import app.state.services
import app.usecases.players
from app.objects.score import Score

# NOTE: this may end up as a class eventually
# if we need score caching or want consistency


async def fetch(score_id: int) -> Optional[Score]:
    """Create a score object from sql using it's scoreid."""
    if row := await app.state.services.database.fetch_one(
        "SELECT scores.id, map_md5, name, pp, score, "
        "max_combo, mods, acc, n300, n100, n50, "
        "nmiss, ngeki, nkatu, grade, perfect, "
        "status, mode, play_time, "
        "time_elapsed, client_flags, online_checksum "
        "FROM scores "
        "INNER JOIN users ON users.id = scores.userid "
        "WHERE scores.id = :score_id",
        {"score_id": score_id},
    ):
        return Score.from_row(row)
