from __future__ import annotations

import math
from typing import Sequence
from typing import TypedDict
from typing import cast

from sqlalchemy import Column
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import func
from sqlalchemy import insert
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.dialects.mysql import FLOAT
from sqlalchemy.dialects.mysql import TINYINT

import app.state.services
from app._typing import UNSET
from app._typing import _UnsetSentinel
from app.repositories import Base


class StatsTable(Base):
    __tablename__ = "stats"

    id = Column("id", Integer, nullable=False, primary_key=True, autoincrement=True)
    mode = Column("mode", TINYINT(1), primary_key=True)
    tscore = Column("tscore", Integer, nullable=False, server_default="0")
    rscore = Column("rscore", Integer, nullable=False, server_default="0")
    pp = Column("pp", Integer, nullable=False, server_default="0")
    pp_total = Column("pp_total", Integer, nullable=False, server_default="0")
    pp_stddev = Column("pp_stddev", Integer, nullable=False, server_default="0")
    plays = Column("plays", Integer, nullable=False, server_default="0")
    playtime = Column("playtime", Integer, nullable=False, server_default="0")
    acc = Column(
        "acc",
        FLOAT(precision=6, scale=3),
        nullable=False,
        server_default="0.000",
    )
    max_combo = Column("max_combo", Integer, nullable=False, server_default="0")
    total_hits = Column("total_hits", Integer, nullable=False, server_default="0")
    replay_views = Column("replay_views", Integer, nullable=False, server_default="0")
    xh_count = Column("xh_count", Integer, nullable=False, server_default="0")
    x_count = Column("x_count", Integer, nullable=False, server_default="0")
    sh_count = Column("sh_count", Integer, nullable=False, server_default="0")
    s_count = Column("s_count", Integer, nullable=False, server_default="0")
    a_count = Column("a_count", Integer, nullable=False, server_default="0")

    __table_args__ = (
        Index("stats_mode_index", mode),
        Index("stats_pp_index", pp),
        Index("stats_total_pp_index", pp_total),
        Index("stats_stddev_pp_index", pp_stddev),
        Index("stats_tscore_index", tscore),
        Index("stats_rscore_index", rscore),
    )


READ_PARAMS = (
    StatsTable.id,
    StatsTable.mode,
    StatsTable.tscore,
    StatsTable.rscore,
    StatsTable.pp,
    StatsTable.pp_total,
    StatsTable.pp_stddev,
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
    pp_total: int
    pp_stddev: int
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


async def fetch_many(
    player_id: int | None = None,
    mode: int | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[Stat]:
    """Fetch multiple player stats entries from the database."""
    select_stmt = select(*READ_PARAMS)

    if player_id is not None:
        select_stmt = select_stmt.where(StatsTable.id == player_id)
    if mode is not None:
        select_stmt = select_stmt.where(StatsTable.mode == mode)

    if page is not None and page_size is not None:
        select_stmt = select_stmt.limit(page_size).offset((page - 1) * page_size)

    stats = await app.state.services.database.fetch_all(select_stmt)

    return cast(list[Stat], stats)


async def partial_update(
    player_id: int,
    mode: int,
    tscore: int | _UnsetSentinel = UNSET,
    rscore: int | _UnsetSentinel = UNSET,
    pp: int | _UnsetSentinel = UNSET,
    pp_total: int | _UnsetSentinel = UNSET,
    pp_stddev: int | _UnsetSentinel = UNSET,
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
    update_stmt = (
        update(StatsTable)
        .where(StatsTable.id == player_id)
        .where(StatsTable.mode == mode)
    )

    if not isinstance(tscore, _UnsetSentinel):
        update_stmt = update_stmt.values(tscore=tscore)
    if not isinstance(rscore, _UnsetSentinel):
        update_stmt = update_stmt.values(rscore=rscore)
    if not isinstance(pp, _UnsetSentinel):
        update_stmt = update_stmt.values(pp=pp)
    if not isinstance(pp_total, _UnsetSentinel):
        update_stmt = update_stmt.values(pp_total=pp_total)
    if not isinstance(pp_stddev, _UnsetSentinel):
        update_stmt = update_stmt.values(pp_stddev=pp_stddev)
    if not isinstance(plays, _UnsetSentinel):
        update_stmt = update_stmt.values(plays=plays)
    if not isinstance(playtime, _UnsetSentinel):
        update_stmt = update_stmt.values(playtime=playtime)
    if not isinstance(acc, _UnsetSentinel):
        update_stmt = update_stmt.values(acc=acc)
    if not isinstance(max_combo, _UnsetSentinel):
        update_stmt = update_stmt.values(max_combo=max_combo)
    if not isinstance(total_hits, _UnsetSentinel):
        update_stmt = update_stmt.values(total_hits=total_hits)
    if not isinstance(replay_views, _UnsetSentinel):
        update_stmt = update_stmt.values(replay_views=replay_views)
    if not isinstance(xh_count, _UnsetSentinel):
        update_stmt = update_stmt.values(xh_count=xh_count)
    if not isinstance(x_count, _UnsetSentinel):
        update_stmt = update_stmt.values(x_count=x_count)
    if not isinstance(sh_count, _UnsetSentinel):
        update_stmt = update_stmt.values(sh_count=sh_count)
    if not isinstance(s_count, _UnsetSentinel):
        update_stmt = update_stmt.values(s_count=s_count)
    if not isinstance(a_count, _UnsetSentinel):
        update_stmt = update_stmt.values(a_count=a_count)

    await app.state.services.database.execute(update_stmt)

    select_stmt = (
        select(*READ_PARAMS)
        .where(StatsTable.id == player_id)
        .where(StatsTable.mode == mode)
    )
    stat = await app.state.services.database.fetch_one(select_stmt)

    return cast(Stat | None, stat)


# TODO: delete?
async def update_rank(
    player_id: int,
    mode: int,
    ranked_score_weighting: int,
    total_score_weighting: int,
    pp_weighting: int,
) -> int:
    """Update a player's stats rank in the database."""
    pp_weighted = (pp_weighting * 0.01) ** 0.5
    rscore_weighted = ranked_score_weighting * 0.01
    tscore_weighted = total_score_weighting * 0.01

    # TODO: this could pretty easily just be one query

    ranking_score = (
        int((StatsTable.pp * pp_weighted) + (StatsTable.rscore * rscore_weighted))
        + int(StatsTable.tscore * tscore_weighted)
    ) * 1000

    # count number of other stats objects with higher rank

    select_stmt = (
        select(func.count())
        .select_from(StatsTable)
        .where(StatsTable.mode == mode)
        .where(ranking_score > ranking_score)
    )
    rank = await app.state.services.database.fetch_val(select_stmt, column=0)

    return cast(int, rank) + 1
