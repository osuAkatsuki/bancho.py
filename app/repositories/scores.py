from __future__ import annotations

from datetime import datetime
from typing import TypedDict
from typing import cast

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import func
from sqlalchemy import insert
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.dialects.mysql import FLOAT
from sqlalchemy.dialects.mysql import TINYINT

import app.state.services
from app._typing import UNSET
from app._typing import _UnsetSentinel
from app.constants.gamemodes import GameMode
from app.repositories import Base


class ScoresTable(Base):
    __tablename__ = "scores"

    id = Column("id", Integer, nullable=False, primary_key=True, autoincrement=True)
    map_md5 = Column("map_md5", String(32), nullable=False)
    score = Column("score", Integer, nullable=False)
    pp = Column("pp", FLOAT(precision=6, scale=3), nullable=False)
    acc = Column("acc", FLOAT(precision=6, scale=3), nullable=False)
    max_combo = Column("max_combo", Integer, nullable=False)
    mods = Column("mods", Integer, nullable=False)
    n300 = Column("n300", Integer, nullable=False)
    n100 = Column("n100", Integer, nullable=False)
    n50 = Column("n50", Integer, nullable=False)
    nmiss = Column("nmiss", Integer, nullable=False)
    ngeki = Column("ngeki", Integer, nullable=False)
    nkatu = Column("nkatu", Integer, nullable=False)
    grade = Column("grade", String(2), nullable=False, server_default="N")
    status = Column("status", Integer, nullable=False)
    mode = Column("mode", Integer, nullable=False)
    play_time = Column("play_time", DateTime, nullable=False)
    time_elapsed = Column("time_elapsed", Integer, nullable=False)
    client_flags = Column("client_flags", Integer, nullable=False)
    userid = Column("userid", Integer, nullable=False)
    perfect = Column("perfect", TINYINT(1), nullable=False)
    online_checksum = Column("online_checksum", String(32), nullable=False)

    __table_args__ = (
        Index("scores_map_md5_index", map_md5),
        Index("scores_score_index", score),
        Index("scores_pp_index", pp),
        Index("scores_mods_index", mods),
        Index("scores_status_index", status),
        Index("scores_mode_index", mode),
        Index("scores_play_time_index", play_time),
        Index("scores_userid_index", userid),
        Index("scores_online_checksum_index", online_checksum),
    )


READ_PARAMS = (
    ScoresTable.id,
    ScoresTable.map_md5,
    ScoresTable.score,
    ScoresTable.pp,
    ScoresTable.acc,
    ScoresTable.max_combo,
    ScoresTable.mods,
    ScoresTable.n300,
    ScoresTable.n100,
    ScoresTable.n50,
    ScoresTable.nmiss,
    ScoresTable.ngeki,
    ScoresTable.nkatu,
    ScoresTable.grade,
    ScoresTable.status,
    ScoresTable.mode,
    ScoresTable.play_time,
    ScoresTable.time_elapsed,
    ScoresTable.client_flags,
    ScoresTable.userid,
    ScoresTable.perfect,
    ScoresTable.online_checksum,
)


class Score(TypedDict):
    id: int
    map_md5: str
    score: int
    pp: float
    acc: float
    max_combo: int
    mods: int
    n300: int
    n100: int
    n50: int
    nmiss: int
    ngeki: int
    nkatu: int
    grade: str
    status: int
    mode: int
    play_time: datetime
    time_elapsed: int
    client_flags: int
    userid: int
    perfect: int
    online_checksum: str


async def create(
    map_md5: str,
    score: int,
    pp: float,
    acc: float,
    max_combo: int,
    mods: int,
    n300: int,
    n100: int,
    n50: int,
    nmiss: int,
    ngeki: int,
    nkatu: int,
    grade: str,
    status: int,
    mode: int,
    play_time: datetime,
    time_elapsed: int,
    client_flags: int,
    user_id: int,
    perfect: int,
    online_checksum: str,
) -> Score:
    insert_stmt = insert(ScoresTable).values(
        map_md5=map_md5,
        score=score,
        pp=pp,
        acc=acc,
        max_combo=max_combo,
        mods=mods,
        n300=n300,
        n100=n100,
        n50=n50,
        nmiss=nmiss,
        ngeki=ngeki,
        nkatu=nkatu,
        grade=grade,
        status=status,
        mode=mode,
        play_time=play_time,
        time_elapsed=time_elapsed,
        client_flags=client_flags,
        userid=user_id,
        perfect=perfect,
        online_checksum=online_checksum,
    )
    rec_id = await app.state.services.database.execute(insert_stmt)

    select_stmt = select(*READ_PARAMS).where(ScoresTable.id == rec_id)
    _score = await app.state.services.database.fetch_one(select_stmt)
    assert _score is not None
    return cast(Score, _score)


async def fetch_one(id: int) -> Score | None:
    select_stmt = select(*READ_PARAMS).where(ScoresTable.id == id)
    _score = await app.state.services.database.fetch_one(select_stmt)
    return cast(Score | None, _score)


async def fetch_recent(user_id: int) -> Score | None:
    select_stmt = (
        select(*READ_PARAMS)
        .where(ScoresTable.userid == user_id)
        .order_by(ScoresTable.id.desc())
        .limit(1)
    )
    _score = await app.state.services.database.fetch_one(select_stmt)
    return cast(Score | None, _score)


async def fetch_count(
    map_md5: str | None = None,
    mods: int | None = None,
    status: int | None = None,
    mode: int | None = None,
    user_id: int | None = None,
) -> int:
    select_stmt = select(func.count().label("count")).select_from(ScoresTable)
    if map_md5 is not None:
        select_stmt = select_stmt.where(ScoresTable.map_md5 == map_md5)
    if mods is not None:
        select_stmt = select_stmt.where(ScoresTable.mods == mods)
    if status is not None:
        select_stmt = select_stmt.where(ScoresTable.status == status)
    if mode is not None:
        select_stmt = select_stmt.where(ScoresTable.mode == mode)
    if user_id is not None:
        select_stmt = select_stmt.where(ScoresTable.userid == user_id)

    rec = await app.state.services.database.fetch_one(select_stmt)
    assert rec is not None
    return cast(int, rec["count"])


async def fetch_many(
    map_md5: str | None = None,
    mods: int | None = None,
    status: int | None = None,
    mode: int | None = None,
    user_id: int | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[Score]:
    select_stmt = select(*READ_PARAMS)
    if map_md5 is not None:
        select_stmt = select_stmt.where(ScoresTable.map_md5 == map_md5)
    if mods is not None:
        select_stmt = select_stmt.where(ScoresTable.mods == mods)
    if status is not None:
        select_stmt = select_stmt.where(ScoresTable.status == status)
    if mode is not None:
        select_stmt = select_stmt.where(ScoresTable.mode == mode)
    if user_id is not None:
        select_stmt = select_stmt.where(ScoresTable.userid == user_id)

    if page is not None and page_size is not None:
        select_stmt = select_stmt.limit(page_size).offset((page - 1) * page_size)

    scores = await app.state.services.database.fetch_all(select_stmt)
    return cast(list[Score], scores)


async def calculate_placement(score: Score) -> int:
    if GameMode(score["mode"]) >= GameMode.RELAX_OSU:
        scoring_metric = "pp"
        scoring = score["pp"]
    else:
        scoring_metric = "score"
        scoring = score["score"]

    num_better_scores: int | None = await app.state.services.database.fetch_val(
        "SELECT COUNT(*) AS c FROM scores s "
        "INNER JOIN users u ON u.id = s.userid "
        "WHERE s.map_md5 = :map_md5 AND s.mode = :mode "
        "AND s.status = 2 AND u.priv & 1 "
        f"AND s.{scoring_metric} > :scoring",
        {
            "map_md5": score["map_md5"],
            "mode": score["mode"],
            "scoring": scoring,
        },
        column=0,  # COUNT(*)
    )
    assert num_better_scores is not None
    return num_better_scores + 1


async def partial_update(
    id: int,
    pp: float | _UnsetSentinel = UNSET,
    status: int | _UnsetSentinel = UNSET,
) -> Score | None:
    """Update an existing score."""
    update_stmt = update(ScoresTable).where(ScoresTable.id == id)
    if not isinstance(pp, _UnsetSentinel):
        update_stmt = update_stmt.values(pp=pp)
    if not isinstance(status, _UnsetSentinel):
        update_stmt = update_stmt.values(status=status)

    await app.state.services.database.execute(update_stmt)

    select_stmt = select(*READ_PARAMS).where(ScoresTable.id == id)
    _score = await app.state.services.database.fetch_one(select_stmt)
    return cast(Score | None, _score)


# TODO: delete
