from __future__ import annotations

from datetime import datetime

def format(
    date: datetime | int | float,
    now: datetime | int | float | None = None,
) -> str: ...
