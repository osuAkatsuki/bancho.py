from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class NominationRequest:
    player_id: int
    map_id: int

    created_at: datetime
    updated_at: Optional[datetime]  # resolved_at? closed_at?
