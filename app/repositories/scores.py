from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pymysql
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import func
from sqlalchemy import insert
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.dialects.mysql import FLOAT
from sqlalchemy.dialects.mysql import TINYINT

from app._typing import UNSET
from app._typing import _UnsetSentinel
from app.adapters.database import Database
from app.adapters.database import MySQLRow
from app.constants.beatmap_statuses import RankedStatus
from app.constants.privileges import Privileges
from app.constants.score_statuses import SubmissionStatus
from app.constants.scoring_metrics import ScoringMetric
from app.repositories import Base
from app.repositories.clans import ClansTable
from app.repositories.maps import MapsTable
from app.repositories.users import UsersTable


class DuplicateScoreError(Exception):
    """Raised when a submitted score already exists."""


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


@dataclass(frozen=True, slots=True)
class Score:
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


@dataclass(frozen=True, slots=True)
class FirstPlaceScore:
    id: int
    name: str


@dataclass(frozen=True, slots=True)
class ScorePerformanceRow:
    pp: float
    acc: float


@dataclass(frozen=True, slots=True)
class BeatmapLeaderboardScoreRow:
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


@dataclass(frozen=True, slots=True)
class PersonalBestLeaderboardScoreRow:
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


@dataclass(frozen=True, slots=True)
class PlayerScoreListingRow:
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
    perfect: int


@dataclass(frozen=True, slots=True)
class MostPlayedMapRow:
    md5: str
    id: int
    set_id: int
    status: int
    artist: str
    title: str
    version: str
    creator: str
    plays: int


@dataclass(frozen=True, slots=True)
class MapScoreListingRow:
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
    userid: int
    perfect: int
    player_name: str
    player_country: str
    clan_id: int | None
    clan_name: str | None
    clan_tag: str | None


@dataclass(frozen=True, slots=True)
class ReplayHeader:
    username: str
    map_md5: str
    artist: str
    title: str
    version: str
    mode: int
    n300: int
    n100: int
    n50: int
    ngeki: int
    nkatu: int
    nmiss: int
    score: int
    max_combo: int
    perfect: int
    mods: int
    play_time: datetime


class ScoresRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def _deserialize_score(self, row: MySQLRow) -> Score:
        return Score(
            id=row["id"],
            map_md5=row["map_md5"],
            score=row["score"],
            pp=row["pp"],
            acc=row["acc"],
            max_combo=row["max_combo"],
            mods=row["mods"],
            n300=row["n300"],
            n100=row["n100"],
            n50=row["n50"],
            nmiss=row["nmiss"],
            ngeki=row["ngeki"],
            nkatu=row["nkatu"],
            grade=row["grade"],
            status=row["status"],
            mode=row["mode"],
            play_time=row["play_time"],
            time_elapsed=row["time_elapsed"],
            client_flags=row["client_flags"],
            userid=row["userid"],
            perfect=row["perfect"],
            online_checksum=row["online_checksum"],
        )

    def _deserialize_first_place_score(self, row: MySQLRow) -> FirstPlaceScore:
        return FirstPlaceScore(
            id=row["id"],
            name=row["name"],
        )

    def _deserialize_score_performance_row(
        self,
        row: MySQLRow,
    ) -> ScorePerformanceRow:
        return ScorePerformanceRow(
            pp=row["pp"],
            acc=row["acc"],
        )

    def _deserialize_beatmap_leaderboard_score_row(
        self,
        row: MySQLRow,
    ) -> BeatmapLeaderboardScoreRow:
        return BeatmapLeaderboardScoreRow(
            id=row["id"],
            leaderboard_value=row["leaderboard_value"],
            max_combo=row["max_combo"],
            n50=row["n50"],
            n100=row["n100"],
            n300=row["n300"],
            nmiss=row["nmiss"],
            nkatu=row["nkatu"],
            ngeki=row["ngeki"],
            perfect=row["perfect"],
            mods=row["mods"],
            time=row["time"],
            userid=row["userid"],
            name=row["name"],
        )

    def _deserialize_personal_best_leaderboard_score_row(
        self,
        row: MySQLRow,
    ) -> PersonalBestLeaderboardScoreRow:
        return PersonalBestLeaderboardScoreRow(
            id=row["id"],
            leaderboard_value=row["leaderboard_value"],
            max_combo=row["max_combo"],
            n50=row["n50"],
            n100=row["n100"],
            n300=row["n300"],
            nmiss=row["nmiss"],
            nkatu=row["nkatu"],
            ngeki=row["ngeki"],
            perfect=row["perfect"],
            mods=row["mods"],
            time=row["time"],
        )

    def _deserialize_player_score_listing_row(
        self,
        row: MySQLRow,
    ) -> PlayerScoreListingRow:
        return PlayerScoreListingRow(
            id=row["id"],
            map_md5=row["map_md5"],
            score=row["score"],
            pp=row["pp"],
            acc=row["acc"],
            max_combo=row["max_combo"],
            mods=row["mods"],
            n300=row["n300"],
            n100=row["n100"],
            n50=row["n50"],
            nmiss=row["nmiss"],
            ngeki=row["ngeki"],
            nkatu=row["nkatu"],
            grade=row["grade"],
            status=row["status"],
            mode=row["mode"],
            play_time=row["play_time"],
            time_elapsed=row["time_elapsed"],
            perfect=row["perfect"],
        )

    def _deserialize_most_played_map_row(
        self,
        row: MySQLRow,
    ) -> MostPlayedMapRow:
        return MostPlayedMapRow(
            md5=row["md5"],
            id=row["id"],
            set_id=row["set_id"],
            status=row["status"],
            artist=row["artist"],
            title=row["title"],
            version=row["version"],
            creator=row["creator"],
            plays=row["plays"],
        )

    def _deserialize_map_score_listing_row(self, row: MySQLRow) -> MapScoreListingRow:
        return MapScoreListingRow(
            id=row["id"],
            map_md5=row["map_md5"],
            score=row["score"],
            pp=row["pp"],
            acc=row["acc"],
            max_combo=row["max_combo"],
            mods=row["mods"],
            n300=row["n300"],
            n100=row["n100"],
            n50=row["n50"],
            nmiss=row["nmiss"],
            ngeki=row["ngeki"],
            nkatu=row["nkatu"],
            grade=row["grade"],
            status=row["status"],
            mode=row["mode"],
            play_time=row["play_time"],
            time_elapsed=row["time_elapsed"],
            userid=row["userid"],
            perfect=row["perfect"],
            player_name=row["player_name"],
            player_country=row["player_country"],
            clan_id=row["clan_id"],
            clan_name=row["clan_name"],
            clan_tag=row["clan_tag"],
        )

    def _deserialize_replay_header(self, row: MySQLRow) -> ReplayHeader:
        return ReplayHeader(
            username=row["username"],
            map_md5=row["map_md5"],
            artist=row["artist"],
            title=row["title"],
            version=row["version"],
            mode=row["mode"],
            n300=row["n300"],
            n100=row["n100"],
            n50=row["n50"],
            ngeki=row["ngeki"],
            nkatu=row["nkatu"],
            nmiss=row["nmiss"],
            score=row["score"],
            max_combo=row["max_combo"],
            perfect=row["perfect"],
            mods=row["mods"],
            play_time=row["play_time"],
        )

    async def create(
        self,
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
        try:
            rec_id = await self._database.execute(insert_stmt)
        except pymysql.err.IntegrityError as exc:
            raise DuplicateScoreError from exc

        select_stmt = select(*READ_PARAMS).where(ScoresTable.id == rec_id)
        _score = await self._database.fetch_one(select_stmt)
        assert _score is not None
        return self._deserialize_score(_score)

    async def mark_previous_best_scores_submitted(
        self,
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
        await self._database.execute(update_stmt)

    async def fetch_weighted_best_performances(
        self,
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

        scores = await self._database.fetch_all(select_stmt)
        return [self._deserialize_score_performance_row(score) for score in scores]

    async def fetch_first_place_score(
        self,
        *,
        map_md5: str,
        mode: int,
        scoring_metric: ScoringMetric,
    ) -> FirstPlaceScore | None:
        leaderboard_value = (
            ScoresTable.pp if scoring_metric == "pp" else ScoresTable.score
        )
        select_stmt = (
            select(UsersTable.id, UsersTable.name)
            .select_from(UsersTable)
            .join(ScoresTable, UsersTable.id == ScoresTable.userid)
            .where(
                ScoresTable.map_md5 == map_md5,
                ScoresTable.mode == mode,
                ScoresTable.status == SubmissionStatus.BEST.value,
                UsersTable.priv.bitwise_and(Privileges.UNRESTRICTED.value) != 0,
            )
            .order_by(leaderboard_value.desc())
            .limit(1)
        )

        first_place_score = await self._database.fetch_one(select_stmt)
        return (
            self._deserialize_first_place_score(first_place_score)
            if first_place_score is not None
            else None
        )

    async def fetch_one_by_online_checksum(self, online_checksum: str) -> Score | None:
        select_stmt = select(*READ_PARAMS).where(
            ScoresTable.online_checksum == online_checksum,
        )
        _score = await self._database.fetch_one(select_stmt)
        return self._deserialize_score(_score) if _score is not None else None

    async def fetch_beatmap_leaderboard_scores(
        self,
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
        leaderboard_value = (
            ScoresTable.pp if scoring_metric == "pp" else ScoresTable.score
        )
        select_stmt = (
            select(
                ScoresTable.id,
                leaderboard_value.label("leaderboard_value"),
                ScoresTable.max_combo,
                ScoresTable.n50,
                ScoresTable.n100,
                ScoresTable.n300,
                ScoresTable.nmiss,
                ScoresTable.nkatu,
                ScoresTable.ngeki,
                ScoresTable.perfect,
                ScoresTable.mods,
                func.unix_timestamp(ScoresTable.play_time).label("time"),
                UsersTable.id.label("userid"),
                func.coalesce(
                    func.concat("[", ClansTable.tag, "] ", UsersTable.name),
                    UsersTable.name,
                ).label("name"),
            )
            .select_from(ScoresTable)
            .join(UsersTable, UsersTable.id == ScoresTable.userid)
            .outerjoin(ClansTable, ClansTable.id == UsersTable.clan_id)
            .where(
                ScoresTable.map_md5 == map_md5,
                ScoresTable.status == SubmissionStatus.BEST.value,
                or_(
                    UsersTable.priv.bitwise_and(Privileges.UNRESTRICTED.value) != 0,
                    UsersTable.id == user_id,
                ),
                ScoresTable.mode == mode,
            )
            .order_by(leaderboard_value.desc())
            .limit(limit)
        )

        if mods is not None:
            select_stmt = select_stmt.where(ScoresTable.mods == mods)
        if friend_ids is not None:
            select_stmt = select_stmt.where(ScoresTable.userid.in_(friend_ids))
        if country is not None:
            select_stmt = select_stmt.where(UsersTable.country == country)

        score_rows = await self._database.fetch_all(select_stmt)
        return [
            self._deserialize_beatmap_leaderboard_score_row(score_row)
            for score_row in score_rows
        ]

    async def fetch_personal_best_leaderboard_score(
        self,
        *,
        map_md5: str,
        mode: int,
        user_id: int,
        scoring_metric: ScoringMetric,
    ) -> PersonalBestLeaderboardScoreRow | None:
        leaderboard_value = (
            ScoresTable.pp if scoring_metric == "pp" else ScoresTable.score
        )
        select_stmt = (
            select(
                ScoresTable.id,
                leaderboard_value.label("leaderboard_value"),
                ScoresTable.max_combo,
                ScoresTable.n50,
                ScoresTable.n100,
                ScoresTable.n300,
                ScoresTable.nmiss,
                ScoresTable.nkatu,
                ScoresTable.ngeki,
                ScoresTable.perfect,
                ScoresTable.mods,
                func.unix_timestamp(ScoresTable.play_time).label("time"),
            )
            .where(
                ScoresTable.map_md5 == map_md5,
                ScoresTable.mode == mode,
                ScoresTable.userid == user_id,
                ScoresTable.status == SubmissionStatus.BEST.value,
            )
            .order_by(leaderboard_value.desc())
            .limit(1)
        )

        personal_best_score_row = await self._database.fetch_one(select_stmt)
        return (
            self._deserialize_personal_best_leaderboard_score_row(
                personal_best_score_row,
            )
            if personal_best_score_row is not None
            else None
        )

    async def fetch_personal_best_leaderboard_rank(
        self,
        *,
        map_md5: str,
        mode: int,
        scoring_metric: ScoringMetric,
        score: int | float,
    ) -> int:
        leaderboard_value = (
            ScoresTable.pp if scoring_metric == "pp" else ScoresTable.score
        )
        select_stmt = (
            select(func.count().label("count"))
            .select_from(ScoresTable)
            .join(UsersTable, UsersTable.id == ScoresTable.userid)
            .where(
                ScoresTable.map_md5 == map_md5,
                ScoresTable.mode == mode,
                ScoresTable.status == SubmissionStatus.BEST.value,
                UsersTable.priv.bitwise_and(Privileges.UNRESTRICTED.value) != 0,
                leaderboard_value > score,
            )
        )

        higher_scores = await self._database.fetch_one(select_stmt)
        assert higher_scores is not None
        return int(higher_scores["count"]) + 1

    async def fetch_player_score_listing_rows(
        self,
        *,
        user_id: int,
        mode: int,
        mods: int | None,
        strong_mods_equality: bool,
        scope: str,
        limit: int,
        include_loved: bool,
        include_failed: bool,
    ) -> list[PlayerScoreListingRow]:
        select_stmt = (
            select(
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
                ScoresTable.perfect,
            )
            .join(MapsTable, ScoresTable.map_md5 == MapsTable.md5)
            .where(
                ScoresTable.userid == user_id,
                ScoresTable.mode == mode,
            )
        )
        if mods is not None:
            mods_match = ScoresTable.mods.bitwise_and(mods)
            if strong_mods_equality:
                select_stmt = select_stmt.where(mods_match == mods)
            else:
                select_stmt = select_stmt.where(mods_match != 0)

        if scope == "best":
            allowed_map_statuses = [
                RankedStatus.Ranked.value,
                RankedStatus.Approved.value,
            ]
            if include_loved:
                allowed_map_statuses.append(RankedStatus.Loved.value)

            select_stmt = select_stmt.where(
                ScoresTable.status == SubmissionStatus.BEST.value,
                MapsTable.status.in_(allowed_map_statuses),
            )
            sort_column = ScoresTable.pp
        else:
            if not include_failed:
                select_stmt = select_stmt.where(
                    ScoresTable.status != SubmissionStatus.FAILED.value,
                )

            sort_column = ScoresTable.play_time

        select_stmt = select_stmt.order_by(sort_column.desc()).limit(limit)

        scores = await self._database.fetch_all(select_stmt)
        return [self._deserialize_player_score_listing_row(score) for score in scores]

    async def fetch_most_played_map_rows(
        self,
        *,
        user_id: int,
        mode: int,
        limit: int,
    ) -> list[MostPlayedMapRow]:
        select_stmt = (
            select(
                MapsTable.md5,
                MapsTable.id,
                MapsTable.set_id,
                MapsTable.status,
                MapsTable.artist,
                MapsTable.title,
                MapsTable.version,
                MapsTable.creator,
                func.count().label("plays"),
            )
            .select_from(ScoresTable)
            .join(MapsTable, MapsTable.md5 == ScoresTable.map_md5)
            .where(
                ScoresTable.userid == user_id,
                ScoresTable.mode == mode,
            )
            .group_by(ScoresTable.map_md5)
            .order_by(func.count().desc())
            .limit(limit)
        )

        maps = await self._database.fetch_all(select_stmt)
        return [self._deserialize_most_played_map_row(map) for map in maps]

    async def fetch_map_score_listing_rows(
        self,
        *,
        map_md5: str,
        mode: int,
        mods: int | None,
        strong_mods_equality: bool,
        scope: str,
        limit: int,
    ) -> list[MapScoreListingRow]:
        select_stmt = (
            select(
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
                ScoresTable.userid,
                ScoresTable.perfect,
                UsersTable.name.label("player_name"),
                UsersTable.country.label("player_country"),
                ClansTable.id.label("clan_id"),
                ClansTable.name.label("clan_name"),
                ClansTable.tag.label("clan_tag"),
            )
            .select_from(ScoresTable)
            .join(UsersTable, UsersTable.id == ScoresTable.userid)
            .outerjoin(ClansTable, ClansTable.id == UsersTable.clan_id)
            .where(
                ScoresTable.map_md5 == map_md5,
                ScoresTable.mode == mode,
                ScoresTable.status == SubmissionStatus.BEST.value,
                UsersTable.priv.bitwise_and(Privileges.UNRESTRICTED.value) != 0,
            )
        )
        if mods is not None:
            mods_match = ScoresTable.mods.bitwise_and(mods)
            if strong_mods_equality:
                select_stmt = select_stmt.where(mods_match == mods)
            else:
                select_stmt = select_stmt.where(mods_match != 0)

        # Unlike /get_player_scores, we sort by score or pp depending on the
        # mode played, since we want to replicate leaderboards.
        if scope == "best":
            sort_column = ScoresTable.pp if mode >= 4 else ScoresTable.score
        else:
            sort_column = ScoresTable.play_time

        select_stmt = select_stmt.order_by(sort_column.desc()).limit(limit)

        scores = await self._database.fetch_all(select_stmt)
        return [self._deserialize_map_score_listing_row(score) for score in scores]

    async def fetch_replay_header(self, score_id: int) -> ReplayHeader | None:
        select_stmt = (
            select(
                UsersTable.name.label("username"),
                MapsTable.md5.label("map_md5"),
                MapsTable.artist,
                MapsTable.title,
                MapsTable.version,
                ScoresTable.mode,
                ScoresTable.n300,
                ScoresTable.n100,
                ScoresTable.n50,
                ScoresTable.ngeki,
                ScoresTable.nkatu,
                ScoresTable.nmiss,
                ScoresTable.score,
                ScoresTable.max_combo,
                ScoresTable.perfect,
                ScoresTable.mods,
                ScoresTable.play_time,
            )
            .select_from(ScoresTable)
            .join(UsersTable, UsersTable.id == ScoresTable.userid)
            .join(MapsTable, MapsTable.md5 == ScoresTable.map_md5)
            .where(ScoresTable.id == score_id)
        )

        replay_header = await self._database.fetch_one(select_stmt)
        return (
            self._deserialize_replay_header(replay_header)
            if replay_header is not None
            else None
        )

    async def fetch_one(self, id: int) -> Score | None:
        select_stmt = select(*READ_PARAMS).where(ScoresTable.id == id)
        _score = await self._database.fetch_one(select_stmt)
        return self._deserialize_score(_score) if _score is not None else None

    async def fetch_count(
        self,
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

        rec = await self._database.fetch_one(select_stmt)
        assert rec is not None
        return int(rec["count"])

    async def fetch_many(
        self,
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

        scores = await self._database.fetch_all(select_stmt)
        return [self._deserialize_score(score) for score in scores]

    async def partial_update(
        self,
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

        await self._database.execute(update_stmt)

        select_stmt = select(*READ_PARAMS).where(ScoresTable.id == id)
        _score = await self._database.fetch_one(select_stmt)
        return self._deserialize_score(_score) if _score is not None else None

    # TODO: delete
