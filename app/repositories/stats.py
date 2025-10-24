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
    total_pp = Column("pp", Integer, nullable=False, server_default="0")
    pp = Column("pp", Integer, nullable=False, server_default="0")
    total_pp = Column("total_pp", Integer, nullable=False, server_default="0")
    stddev_pp = Column("stddev_pp", Integer, nullable=False, server_default="0")
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
        Index("stats_total_pp_index", total_pp),
        Index("stats_stddev_pp_index", stddev_pp),
        Index("stats_tscore_index", tscore),
        Index("stats_rscore_index", rscore),
    )
READ_PARAMS = (
    StatsTable.id,
    StatsTable.mode,
    StatsTable.tscore,
    StatsTable.rscore,
    StatsTable.pp,
    StatsTable.total_pp,
    StatsTable.stddev_pp,
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
    total_pp: int
    stddev_pp: int
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
async def create(player_id: int, mode: int) -> Stat:
    """Create a new player stats entry in the database."""
    insert_stmt = insert(StatsTable).values(id=player_id, mode=mode)
    rec_id = await app.state.services.database.execute(insert_stmt)
    select_stmt = select(*READ_PARAMS).where(StatsTable.id == rec_id)
    stat = await app.state.services.database.fetch_one(select_stmt)
    assert stat is not None
    return cast(Stat, stat)
async def create_all_modes(player_id: int) -> list[Stat]:
    """Create new player stats entries for each game mode in the database."""
    insert_stmt = insert(StatsTable).values(
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
    await app.state.services.database.execute(insert_stmt)
    select_stmt = select(*READ_PARAMS).where(StatsTable.id == player_id)
    stats = await app.state.services.database.fetch_all(select_stmt)
    return cast(list[Stat], stats)
async def fetch_one(player_id: int, mode: int) -> Stat | None:
    """Fetch a player stats entry from the database."""
    select_stmt = (
        select(*READ_PARAMS)
        .where(StatsTable.id == player_id)
        .where(StatsTable.mode == mode)
    )
    stat = await app.state.services.database.fetch_one(select_stmt)
    return cast(Stat | None, stat)
async def fetch_count(
    player_id: int | None = None,
    mode: int | None = None,
) -> int:
    select_stmt = select(func.count().label("count")).select_from(StatsTable)
    if player_id is not None:
        select_stmt = select_stmt.where(StatsTable.id == player_id)
    if mode is not None:
        select_stmt = select_stmt.where(StatsTable.mode == mode)
    rec = await app.state.services.database.fetch_one(select_stmt)
    assert rec is not None
    return cast(int, rec["count"])
async def fetch_many(
    player_id: int | None = None,
    mode: int | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[Stat]:
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
    total_pp: int | _UnsetSentinel = UNSET,
    stddev_pp: int | _UnsetSentinel = UNSET,
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
    if not isinstance(total_pp, _UnsetSentinel):
        update_stmt = update_stmt.values(total_pp=total_pp)
    if not isinstance(stddev_pp, _UnsetSentinel):
        update_stmt = update_stmt.values(stddev_pp=stddev_pp)
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


async def recalculate_total_and_stddev_pp(player_id: int) -> None:
    """Recalculate total_pp and stddev_pp for a player across all modes."""
    # Fetch all 8 mode stats for the player
    # Modes: 0=std, 1=taiko, 2=catch, 3=mania, 4=rx!std, 5=rx!taiko, 6=rx!catch, 8=ap!std
    select_stmt = select(*READ_PARAMS).where(StatsTable.id == player_id)
    stats = await app.state.services.database.fetch_all(select_stmt)

    if not stats:
        return

    # Collect PP values from each mode
    pp_values = []
    stats_by_mode = {stat["mode"]: stat for stat in stats}

    for mode in [0, 1, 2, 3, 4, 5, 6, 8]:
        if mode in stats_by_mode:
            pp_values.append(stats_by_mode[mode]["pp"])
        else:
            pp_values.append(0)

    # Calculate total_pp (sum of all 8 modes)
    total_pp = int(sum(pp_values))

    # Calculate stddev_pp: total_pp - 2 * sqrt(variance/7)
    # where variance = sum((x - mean)^2) for x in pp_values
    # and mean = total_pp / 8
    if total_pp == 0:
        stddev_pp = 0
    else:
        mean_pp = total_pp / 8
        variance = sum((x - mean_pp) ** 2 for x in pp_values)
        stddev_pp = int(total_pp - 2 * math.sqrt(variance / 7))
        stddev_pp = max(0, stddev_pp)  # Ensure non-negative

    # Update all modes with the new total_pp and stddev_pp values
    for mode in [0, 1, 2, 3, 4, 5, 6, 8]:
        update_stmt = (
            update(StatsTable)
            .where(StatsTable.id == player_id)
            .where(StatsTable.mode == mode)
            .values(total_pp=total_pp, stddev_pp=stddev_pp)
        )
        await app.state.services.database.execute(update_stmt)



# TODO: delete?
