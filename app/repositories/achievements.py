from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING
from typing import Any
from typing import TypedDict
from typing import cast

import app.state.services
from app._typing import UNSET
from app._typing import _UnsetSentinel
from app.repositories import DIALECT
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
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy import update


class AchievementsTable(Base):
    __tablename__ = "achievements"

    id = Column("id", Integer, primary_key=True)
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
    stmt = insert(AchievementsTable).values(file=file, name=name, desc=desc, cond=cond)
    compiled = stmt.compile(dialect=DIALECT)

    rec_id = await app.state.services.database.execute(str(compiled), compiled.params)

    stmt = select(*READ_PARAMS).where(AchievementsTable.id == rec_id)
    compiled = stmt.compile(dialect=DIALECT)

    rec = await app.state.services.database.fetch_one(str(compiled), compiled.params)
    assert rec is not None

    achievement = dict(rec._mapping)
    achievement["cond"] = eval(f'lambda score, mode_vn: {rec["cond"]}')
    return cast(Achievement, achievement)


async def fetch_one(
    id: int | None = None,
    name: str | None = None,
) -> Achievement | None:
    """Fetch a single achievement."""
    if id is None and name is None:
        raise ValueError("Must provide at least one parameter.")

    where_conditions = []
    if id is not None:
        where_conditions.append(AchievementsTable.id == id)
    if name is not None:
        where_conditions.append(AchievementsTable.name == name)

    # TODO: wtf?
    stmt = select(*READ_PARAMS).where(or_(*where_conditions))
    compiled = stmt.compile(dialect=DIALECT)
    rec = await app.state.services.database.fetch_one(str(compiled), compiled.params)

    if rec is None:
        return None

    achievement = dict(rec._mapping)
    achievement["cond"] = eval(f'lambda score, mode_vn: {rec["cond"]}')
    return cast(Achievement, achievement)


async def fetch_count() -> int:
    """Fetch the number of achievements."""
    stmt = select(func.count().label("count")).select_from(AchievementsTable)
    compiled = stmt.compile(dialect=DIALECT)

    rec = await app.state.services.database.fetch_one(str(compiled), compiled.params)
    assert rec is not None
    return cast(int, rec._mapping["count"])


async def fetch_many(
    page: int | None = None,
    page_size: int | None = None,
) -> list[Achievement]:
    """Fetch a list of achievements."""
    stmt = select(*READ_PARAMS)
    if page is not None and page_size is not None:
        stmt = stmt.limit(page_size).offset((page - 1) * page_size)

    compiled = stmt.compile(dialect=DIALECT)

    records = await app.state.services.database.fetch_all(
        str(compiled),
        compiled.params,
    )

    achievements: list[dict[str, Any]] = []

    for rec in records:
        achievement = dict(rec._mapping)
        achievement["cond"] = eval(f'lambda score, mode_vn: {rec["cond"]}')
        achievements.append(achievement)

    return cast(list[Achievement], achievements)


async def partial_update(
    id: int,
    file: str | _UnsetSentinel = UNSET,
    name: str | _UnsetSentinel = UNSET,
    desc: str | _UnsetSentinel = UNSET,
    cond: str | _UnsetSentinel = UNSET,
) -> Achievement | None:
    """Update an existing achievement."""
    stmt = update(AchievementsTable).where(AchievementsTable.id == id)
    if not isinstance(file, _UnsetSentinel):
        stmt = stmt.values(file=file)
    if not isinstance(name, _UnsetSentinel):
        stmt = stmt.values(name=name)
    if not isinstance(desc, _UnsetSentinel):
        stmt = stmt.values(desc=desc)
    if not isinstance(cond, _UnsetSentinel):
        stmt = stmt.values(cond=cond)

    compiled = stmt.compile(dialect=DIALECT)
    await app.state.services.database.execute(str(compiled), compiled.params)

    stmt = select(*READ_PARAMS).where(AchievementsTable.id == id)
    compiled = stmt.compile(dialect=DIALECT)
    rec = await app.state.services.database.fetch_one(str(compiled), compiled.params)
    assert rec is not None

    achievement = dict(rec._mapping)
    achievement["cond"] = eval(f'lambda score, mode_vn: {rec["cond"]}')
    return cast(Achievement, achievement)


async def delete_one(
    id: int,
) -> Achievement | None:
    """Delete an existing achievement."""
    stmt = select(*READ_PARAMS).where(AchievementsTable.id == id)
    compiled = stmt.compile(dialect=DIALECT)
    rec = await app.state.services.database.fetch_one(str(compiled), compiled.params)
    if rec is None:
        return None

    stmt = delete(AchievementsTable).where(AchievementsTable.id == id)
    compiled = stmt.compile(dialect=DIALECT)
    await app.state.services.database.execute(str(compiled), compiled.params)

    achievement = dict(rec._mapping)
    achievement["cond"] = eval(f'lambda score, mode_vn: {rec["cond"]}')
    return cast(Achievement, achievement)
