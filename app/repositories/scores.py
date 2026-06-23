from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any
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
from app.constants.beatmap_statuses import RankedStatus
from app.constants.privileges import Privileges
from app.constants.score_statuses import SubmissionStatus
from app.constants.scoring_metrics import ScoringMetric
from app.repositories import Base
from app.repositories.maps import MapsTable


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


class PreviousFirstPlace(TypedDict):
    id: int
    name: str


class ScorePerformanceRow(TypedDict):
    pp: float
    acc: float


class BeatmapLeaderboardScoreRow(TypedDict):
    id: int
    # score or pp, depending on the requested ScoringMetric.
    leaderboard_value: int | float
    max_combo: int
    n50: int
    n100: int
    n300: int
    nmiss: int
    nkatu: int
    ngeki: int
    perfect: int
    mods: int
    time: int
    userid: int
    name: str


class PersonalBestLeaderboardScoreRow(TypedDict):
    id: int
    # score or pp, depending on the requested ScoringMetric.
    leaderboard_value: int | float
    max_combo: int
    n50: int
    n100: int
    n300: int
    nmiss: int
    nkatu: int
    ngeki: int
    perfect: int
    mods: int
    time: int


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


async def mark_previous_best_scores_submitted(
    *,
    map_md5: str,
    user_id: int,
    mode: int,
) -> None:
    update_stmt = (
        update(ScoresTable)
        .where(
            ScoresTable.status == SubmissionStatus.BEST.value,
            ScoresTable.map_md5 == map_md5,
            ScoresTable.userid == user_id,
            ScoresTable.mode == mode,
        )
        .values(status=SubmissionStatus.SUBMITTED.value)
    )
    await app.state.services.database.execute(update_stmt)


async def fetch_weighted_best_performances(
    *,
    user_id: int,
    mode: int,
) -> list[ScorePerformanceRow]:
    select_stmt = (
        select(ScoresTable.pp, ScoresTable.acc)
        .join(MapsTable, ScoresTable.map_md5 == MapsTable.md5)
        .where(
            ScoresTable.userid == user_id,
            ScoresTable.mode == mode,
            ScoresTable.status == SubmissionStatus.BEST.value,
            MapsTable.status.in_(
                (
                    RankedStatus.Ranked.value,
                    RankedStatus.Approved.value,
                ),
            ),
        )
        .order_by(ScoresTable.pp.desc())
    )

    scores = await app.state.services.database.fetch_all(select_stmt)
    return cast(list[ScorePerformanceRow], scores)


async def fetch_previous_first_place(
    *,
    map_md5: str,
    mode: int,
    scoring_metric: ScoringMetric,
) -> PreviousFirstPlace | None:
    previous_first_place = await app.state.services.database.fetch_one(
        "SELECT u.id, name FROM users u "
        "INNER JOIN scores s ON u.id = s.userid "
        "WHERE s.map_md5 = :map_md5 AND s.mode = :mode "
        "AND s.status = :status AND u.priv & :unrestricted_priv "
        f"ORDER BY s.{scoring_metric} DESC LIMIT 1",
        {
            "map_md5": map_md5,
            "mode": mode,
            "status": SubmissionStatus.BEST.value,
            "unrestricted_priv": Privileges.UNRESTRICTED.value,
        },
    )
    return cast(PreviousFirstPlace | None, previous_first_place)


async def fetch_beatmap_leaderboard_scores(
    *,
    map_md5: str,
    mode: int,
    user_id: int,
    scoring_metric: ScoringMetric,
    mods: int | None = None,
    friend_ids: set[int] | None = None,
    country: str | None = None,
    limit: int = 50,
) -> list[BeatmapLeaderboardScoreRow]:
    query = [
        f"SELECT s.id, s.{scoring_metric} AS leaderboard_value, "
        "s.max_combo, s.n50, s.n100, s.n300, "
        "s.nmiss, s.nkatu, s.ngeki, s.perfect, s.mods, "
        "UNIX_TIMESTAMP(s.play_time) time, u.id userid, "
        "COALESCE(CONCAT('[', c.tag, '] ', u.name), u.name) AS name "
        "FROM scores s "
        "INNER JOIN users u ON u.id = s.userid "
        "LEFT JOIN clans c ON c.id = u.clan_id "
        "WHERE s.map_md5 = :map_md5 AND s.status = :status "
        "AND (u.priv & :unrestricted_priv OR u.id = :user_id) "
        "AND mode = :mode",
    ]

    params: dict[str, Any] = {
        "map_md5": map_md5,
        "user_id": user_id,
        "mode": mode,
        "status": SubmissionStatus.BEST.value,
        "unrestricted_priv": Privileges.UNRESTRICTED.value,
        "limit": limit,
    }

    if mods is not None:
        query.append("AND s.mods = :mods")
        params["mods"] = mods
    if friend_ids is not None:
        query.append("AND s.userid IN :friends")
        params["friends"] = friend_ids
    if country is not None:
        query.append("AND u.country = :country")
        params["country"] = country

    query.append("ORDER BY leaderboard_value DESC LIMIT :limit")

    score_rows = await app.state.services.database.fetch_all(" ".join(query), params)
    return [cast(BeatmapLeaderboardScoreRow, dict(row)) for row in score_rows]


async def fetch_personal_best_leaderboard_score(
    *,
    map_md5: str,
    mode: int,
    user_id: int,
    scoring_metric: ScoringMetric,
) -> PersonalBestLeaderboardScoreRow | None:
    personal_best_score_row = await app.state.services.database.fetch_one(
        f"SELECT id, {scoring_metric} AS leaderboard_value, "
        "max_combo, n50, n100, n300, "
        "nmiss, nkatu, ngeki, perfect, mods, "
        "UNIX_TIMESTAMP(play_time) time "
        "FROM scores "
        "WHERE map_md5 = :map_md5 AND mode = :mode "
        "AND userid = :user_id AND status = :status "
        "ORDER BY leaderboard_value DESC LIMIT 1",
        {
            "map_md5": map_md5,
            "mode": mode,
            "user_id": user_id,
            "status": SubmissionStatus.BEST.value,
        },
    )
    return (
        cast(PersonalBestLeaderboardScoreRow, dict(personal_best_score_row))
        if personal_best_score_row is not None
        else None
    )


async def fetch_personal_best_leaderboard_rank(
    *,
    map_md5: str,
    mode: int,
    scoring_metric: ScoringMetric,
    score: int | float,
) -> int:
    higher_scores = await app.state.services.database.fetch_val(
        "SELECT COUNT(*) FROM scores s "
        "INNER JOIN users u ON u.id = s.userid "
        "WHERE s.map_md5 = :map_md5 AND s.mode = :mode "
        "AND s.status = :status AND u.priv & :unrestricted_priv "
        f"AND s.{scoring_metric} > :score",
        {
            "map_md5": map_md5,
            "mode": mode,
            "score": score,
            "status": SubmissionStatus.BEST.value,
            "unrestricted_priv": Privileges.UNRESTRICTED.value,
        },
        column=0,
    )
    assert higher_scores is not None
    return int(higher_scores) + 1


async def fetch_one(id: int) -> Score | None:
    select_stmt = select(*READ_PARAMS).where(ScoresTable.id == id)
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
