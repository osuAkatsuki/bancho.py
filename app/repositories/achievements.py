from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING
from typing import TypedDict
from typing import cast

import app.state.services
from app._typing import UNSET
from app._typing import _UnsetSentinel
from app.repositories import Base

if TYPE_CHECKING:
    from app.objects.score import Score

from sqlalchemy import Column
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import delete
from sqlalchemy import func
from sqlalchemy import insert
from sqlalchemy import select
from sqlalchemy import update


class AchievementsTable(Base):
    __tablename__ = "achievements"

    id = Column("id", Integer, primary_key=True, nullable=False, autoincrement=True)
    file = Column("file", String(128), nullable=False)
    name = Column("name", String(128, collation="utf8"), nullable=False)
    desc = Column("desc", String(256, collation="utf8"), nullable=False)
    cond = Column("cond", String(64), nullable=False)

    __table_args__ = (
        Index("achievements_desc_uindex", desc, unique=True),
        Index("achievements_file_uindex", file, unique=True),
        Index("achievements_name_uindex", name, unique=True),
    )


READ_PARAMS = (
    AchievementsTable.id,
    AchievementsTable.file,
    AchievementsTable.name,
    AchievementsTable.desc,
    AchievementsTable.cond,
)


class Achievement(TypedDict):
    id: int
    file: str
    name: str
    desc: str
    cond: Callable[[Score, int], bool]


async def create(
    file: str,
    name: str,
    desc: str,
    cond: str,
) -> Achievement:
    """Create a new achievement."""
    insert_stmt = insert(AchievementsTable).values(
        file=file,
        name=name,
        desc=desc,
        cond=cond,
    )
    rec_id = await app.state.services.database.execute(insert_stmt)

    select_stmt = select(*READ_PARAMS).where(AchievementsTable.id == rec_id)
    achievement = await app.state.services.database.fetch_one(select_stmt)
    assert achievement is not None

    achievement["cond"] = eval(f'lambda score, mode_vn: {achievement["cond"]}')
    return cast(Achievement, achievement)


async def fetch_one(
    id: int | None = None,
    name: str | None = None,
) -> Achievement | None:
    """Fetch a single achievement."""
    if id is None and name is None:
        raise ValueError("Must provide at least one parameter.")

    select_stmt = select(*READ_PARAMS)

    if id is not None:
        select_stmt = select_stmt.where(AchievementsTable.id == id)
    if name is not None:
        select_stmt = select_stmt.where(AchievementsTable.name == name)

    achievement = await app.state.services.database.fetch_one(select_stmt)
    if achievement is None:
        return None

    achievement["cond"] = eval(f'lambda score, mode_vn: {achievement["cond"]}')
    return cast(Achievement, achievement)


async def fetch_count() -> int:
    """Fetch the number of achievements."""
    select_stmt = select(func.count().label("count")).select_from(AchievementsTable)

    rec = await app.state.services.database.fetch_one(select_stmt)
    assert rec is not None
    return cast(int, rec["count"])


async def fetch_many(
    page: int | None = None,
    page_size: int | None = None,
) -> list[Achievement]:
    """Fetch a list of achievements."""
    select_stmt = select(*READ_PARAMS)
    if page is not None and page_size is not None:
        select_stmt = select_stmt.limit(page_size).offset((page - 1) * page_size)

    achievements = await app.state.services.database.fetch_all(select_stmt)
    for achievement in achievements:
        achievement["cond"] = eval(f'lambda score, mode_vn: {achievement["cond"]}')

    return cast(list[Achievement], achievements)


async def partial_update(
    id: int,
    file: str | _UnsetSentinel = UNSET,
    name: str | _UnsetSentinel = UNSET,
    desc: str | _UnsetSentinel = UNSET,
    cond: str | _UnsetSentinel = UNSET,
) -> Achievement | None:
    """Update an existing achievement."""
    update_stmt = update(AchievementsTable).where(AchievementsTable.id == id)
    if not isinstance(file, _UnsetSentinel):
        update_stmt = update_stmt.values(file=file)
    if not isinstance(name, _UnsetSentinel):
        update_stmt = update_stmt.values(name=name)
    if not isinstance(desc, _UnsetSentinel):
        update_stmt = update_stmt.values(desc=desc)
    if not isinstance(cond, _UnsetSentinel):
        update_stmt = update_stmt.values(cond=cond)

    await app.state.services.database.execute(update_stmt)

    select_stmt = select(*READ_PARAMS).where(AchievementsTable.id == id)
    achievement = await app.state.services.database.fetch_one(select_stmt)
    if achievement is None:
        return None

    achievement["cond"] = eval(f'lambda score, mode_vn: {achievement["cond"]}')
    return cast(Achievement, achievement)


async def delete_one(
    id: int,
) -> Achievement | None:
    """Delete an existing achievement."""
    select_stmt = select(*READ_PARAMS).where(AchievementsTable.id == id)
    achievement = await app.state.services.database.fetch_one(select_stmt)
    if achievement is None:
        return None

    delete_stmt = delete(AchievementsTable).where(AchievementsTable.id == id)
    await app.state.services.database.execute(delete_stmt)

    achievement["cond"] = eval(f'lambda score, mode_vn: {achievement["cond"]}')
    return cast(Achievement, achievement)
