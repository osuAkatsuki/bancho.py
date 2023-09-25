from __future__ import annotations

import app.repositories.achievements
from app.repositories.achievements import Achievement


async def create(
    file: str,
    name: str,
    desc: str,
    cond: str,
) -> Achievement:
    achievement = await app.repositories.achievements.create(
        file,
        name,
        desc,
        cond,
    )
    return achievement


async def fetch_many(
    page: int | None = None,
    page_size: int | None = None,
) -> list[Achievement]:
    achievements = await app.repositories.achievements.fetch_many(
        page,
        page_size,
    )
    return achievements
