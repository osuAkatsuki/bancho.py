from __future__ import annotations

import app.repositories.user_achievements
from app._typing import UNSET
from app._typing import _UnsetSentinel
from app.repositories.user_achievements import UserAchievement


async def create(user_id: int, achievement_id: int) -> UserAchievement:
    user_achievement = await app.repositories.user_achievements.create(
        user_id,
        achievement_id,
    )
    return user_achievement


async def fetch_many(
    user_id: int | _UnsetSentinel = UNSET,
    page: int | None = None,
    page_size: int | None = None,
) -> list[UserAchievement]:
    user_achievements = await app.repositories.user_achievements.fetch_many(
        user_id=user_id,
        page=page,
        page_size=page_size,
    )
    return user_achievements
