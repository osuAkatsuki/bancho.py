from __future__ import annotations

from typing import TypedDict
from typing import cast

from sqlalchemy import Column
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import func
from sqlalchemy import insert
from sqlalchemy import select
from sqlalchemy import update

# from sqlalchemy import update
from sqlalchemy.dialects.mysql import FLOAT
from sqlalchemy.dialects.mysql import TINYINT

import app.state.services
from app._typing import UNSET
from app._typing import _UnsetSentinel
from app.repositories import DIALECT
from app.repositories import Base


class StatsTable(Base):
    __tablename__ = "stats"

    id = Column("id", Integer, primary_key=True)
    mode = Column("mode", TINYINT(1), primary_key=True)
    tscore = Column("tscore", Integer, nullable=False, default=0)
    rscore = Column("rscore", Integer, nullable=False, default=0)
    pp = Column("pp", Integer, nullable=False, default=0)
    plays = Column("plays", Integer, nullable=False, default=0)
    playtime = Column("playtime", Integer, nullable=False, default=0)
    acc = Column("acc", FLOAT(precision=6, scale=3), nullable=False, default=0.000)
    max_combo = Column("max_combo", Integer, nullable=False, default=0)
    total_hits = Column("total_hits", Integer, nullable=False, default=0)
    replay_views = Column("replay_views", Integer, nullable=False, default=0)
    xh_count = Column("xh_count", Integer, nullable=False, default=0)
    x_count = Column("x_count", Integer, nullable=False, default=0)
    sh_count = Column("sh_count", Integer, nullable=False, default=0)
    s_count = Column("s_count", Integer, nullable=False, default=0)
    a_count = Column("a_count", Integer, nullable=False, default=0)

    __table_args__ = (
        Index("stats_mode_index", mode),
        Index("stats_pp_index", pp),
        Index("stats_tscore_index", tscore),
        Index("stats_rscore_index", rscore),
    )


READ_PARAMS = (
    StatsTable.id,
    StatsTable.mode,
    StatsTable.tscore,
    StatsTable.rscore,
    StatsTable.pp,
    StatsTable.plays,
    StatsTable.playtime,
    StatsTable.acc,
    StatsTable.max_combo,
    StatsTable.total_hits,
    StatsTable.replay_views,
    StatsTable.xh_count,
    StatsTable.x_count,
    StatsTable.sh_count,
    StatsTable.s_count,
    StatsTable.a_count,
)


class Stat(TypedDict):
    id: int
    mode: int
    tscore: int
    rscore: int
    pp: int
    plays: int
    playtime: int
    acc: float
    max_combo: int
    total_hits: int
    replay_views: int
    xh_count: int
    x_count: int
    sh_count: int
    s_count: int
    a_count: int


# class StatUpdateFields(TypedDict, total=False):
#     tscore: int
#     rscore: int
#     pp: int
#     plays: int
#     playtime: int
#     acc: float
#     max_combo: int
#     total_hits: int
#     replay_views: int
#     xh_count: int
#     x_count: int
#     sh_count: int
#     s_count: int
#     a_count: int


async def create(player_id: int, mode: int) -> Stat:
    """Create a new player stats entry in the database."""
    stmt = insert(StatsTable).values(id=player_id, mode=mode)
    compiled = stmt.compile(dialect=DIALECT)
    rec_id = await app.state.services.database.execute(
        query=str(compiled),
        values=compiled.params,
    )

    stmt = select(READ_PARAMS).where(StatsTable.id == rec_id)
    compiled = stmt.compile(dialect=DIALECT)
    stat = await app.state.services.database.fetch_one(
        query=str(compiled),
        values=compiled.params,
    )
    assert stat is not None
    return cast(Stat, dict(stat._mapping))


async def create_all_modes(player_id: int) -> list[Stat]:
    """Create new player stats entries for each game mode in the database."""
    stmt = insert(StatsTable).values(
        [
            {"id": player_id, "mode": mode}
            for mode in (
                0,  # vn!std
                1,  # vn!taiko
                2,  # vn!catch
                3,  # vn!mania
                4,  # rx!std
                5,  # rx!taiko
                6,  # rx!catch
                8,  # ap!std
            )
        ],
    )
    compiled = stmt.compile(dialect=DIALECT)
    await app.state.services.database.execute(str(compiled), compiled.params)

    stmt = select(READ_PARAMS).where(StatsTable.id == player_id)
    compiled = stmt.compile(dialect=DIALECT)
    stats = await app.state.services.database.fetch_all(
        query=str(compiled),
        values=compiled.params,
    )
    return cast(list[Stat], [dict(s._mapping) for s in stats])


async def fetch_one(player_id: int, mode: int) -> Stat | None:
    """Fetch a player stats entry from the database."""
    stmt = (
        select(READ_PARAMS)
        .where(StatsTable.id == player_id)
        .where(StatsTable.mode == mode)
    )
    compiled = stmt.compile(dialect=DIALECT)
    stat = await app.state.services.database.fetch_one(
        query=str(compiled),
        values=compiled.params,
    )
    return cast(Stat, dict(stat._mapping)) if stat is not None else None


async def fetch_count(
    player_id: int | None = None,
    mode: int | None = None,
) -> int:
    stmt = select(func.count().label("count")).select_from(StatsTable)
    if player_id is not None:
        stmt = stmt.where(StatsTable.id == player_id)
    if mode is not None:
        stmt = stmt.where(StatsTable.mode == mode)
    compiled = stmt.compile(dialect=DIALECT)
    rec = await app.state.services.database.fetch_one(
        query=str(compiled),
        values=compiled.params,
    )
    assert rec is not None
    return cast(int, rec._mapping["count"])


async def fetch_many(
    player_id: int | None = None,
    mode: int | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[Stat]:
    stmt = select(READ_PARAMS)
    if player_id is not None:
        stmt = stmt.where(StatsTable.id == player_id)
    if mode is not None:
        stmt = stmt.where(StatsTable.mode == mode)
    if page is not None and page_size is not None:
        stmt = stmt.limit(page_size).offset((page - 1) * page_size)
    compiled = stmt.compile(dialect=DIALECT)
    stats = await app.state.services.database.fetch_all(
        query=str(compiled),
        values=compiled.params,
    )
    return cast(list[Stat], [dict(s._mapping) for s in stats])


async def partial_update(
    player_id: int,
    mode: int,
    tscore: int | _UnsetSentinel = UNSET,
    rscore: int | _UnsetSentinel = UNSET,
    pp: int | _UnsetSentinel = UNSET,
    plays: int | _UnsetSentinel = UNSET,
    playtime: int | _UnsetSentinel = UNSET,
    acc: float | _UnsetSentinel = UNSET,
    max_combo: int | _UnsetSentinel = UNSET,
    total_hits: int | _UnsetSentinel = UNSET,
    replay_views: int | _UnsetSentinel = UNSET,
    xh_count: int | _UnsetSentinel = UNSET,
    x_count: int | _UnsetSentinel = UNSET,
    sh_count: int | _UnsetSentinel = UNSET,
    s_count: int | _UnsetSentinel = UNSET,
    a_count: int | _UnsetSentinel = UNSET,
) -> Stat | None:
    """Update a player stats entry in the database."""
    stmt = (
        update(StatsTable)
        .where(StatsTable.id == player_id)
        .where(StatsTable.mode == mode)
    )
    if not isinstance(tscore, _UnsetSentinel):
        stmt = stmt.values(tscore=tscore)
    if not isinstance(rscore, _UnsetSentinel):
        stmt = stmt.values(rscore=rscore)
    if not isinstance(pp, _UnsetSentinel):
        stmt = stmt.values(pp=pp)
    if not isinstance(plays, _UnsetSentinel):
        stmt = stmt.values(plays=plays)
    if not isinstance(playtime, _UnsetSentinel):
        stmt = stmt.values(playtime=playtime)
    if not isinstance(acc, _UnsetSentinel):
        stmt = stmt.values(acc=acc)
    if not isinstance(max_combo, _UnsetSentinel):
        stmt = stmt.values(max_combo=max_combo)
    if not isinstance(total_hits, _UnsetSentinel):
        stmt = stmt.values(total_hits=total_hits)
    if not isinstance(replay_views, _UnsetSentinel):
        stmt = stmt.values(replay_views=replay_views)
    if not isinstance(xh_count, _UnsetSentinel):
        stmt = stmt.values(xh_count=xh_count)
    if not isinstance(x_count, _UnsetSentinel):
        stmt = stmt.values(x_count=x_count)
    if not isinstance(sh_count, _UnsetSentinel):
        stmt = stmt.values(sh_count=sh_count)
    if not isinstance(s_count, _UnsetSentinel):
        stmt = stmt.values(s_count=s_count)
    if not isinstance(a_count, _UnsetSentinel):
        stmt = stmt.values(a_count=a_count)

    compiled = stmt.compile(dialect=DIALECT)
    await app.state.services.database.execute(str(compiled), compiled.params)

    stmt = (
        select(READ_PARAMS)
        .where(StatsTable.id == player_id)
        .where(StatsTable.mode == mode)
    )
    compiled = stmt.compile(dialect=DIALECT)
    stat = await app.state.services.database.fetch_one(
        query=str(compiled),
        values=compiled.params,
    )
    return cast(Stat, dict(stat._mapping)) if stat is not None else None


# TODO: delete?
