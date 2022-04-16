from __future__ import annotations

from pathlib import Path
from typing import Optional

import app.repositories.scores
import app.usecases.scores

REPLAYS_PATH = Path.cwd() / ".data/osr"


async def fetch_file(score_id: int) -> Optional[Path]:
    """Fetch a replay file for a given score id."""
    score = await app.repositories.scores.fetch(score_id)
    if not score:
        return

    file = REPLAYS_PATH / f"{score_id}.osr"
    if file.exists():
        return file

    return None
