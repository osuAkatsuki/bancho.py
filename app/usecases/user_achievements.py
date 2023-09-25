from __future__ import annotations

import app.repositories.user_achievements
from app._typing import _UnsetSentinel
from app._typing import UNSET
from app.repositories.user_achievements import UserAchievement


async def create(user_id: int, achievement_id: int) -> UserAchievement:
    user_achievement = await app.repositories.user_achievements.create(
        user_id,
        achievement_id,
    )
    return user_achievement


async def fetch_many(
    user_id: int,
    page: int | _UnsetSentinel = UNSET,
    page_size: int | _UnsetSentinel = UNSET,
) -> list[UserAchievement]:
    user_achievements = await app.repositories.user_achievements.fetch_many(
        user_id,
        page,
        page_size,
    )
    return user_achievements
