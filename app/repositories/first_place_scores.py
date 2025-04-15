from __future__ import annotations

from typing import TypedDict
from typing import cast

from sqlalchemy import Column
from sqlalchemy import Index
from sqlalchemy import BigInteger
from sqlalchemy import SmallInteger
from sqlalchemy import String
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy import select
from sqlalchemy import and_
from sqlalchemy import PrimaryKeyConstraint

import app.state.services
from app.repositories import Base
from app.constants.gamemodes import GameMode


class FirstPlaceScoresTable(Base):
    __tablename__ = "first_place_scores"

    map_md5 = Column("map_md5", String(32), nullable=False)
    mode = Column("mode", SmallInteger, nullable=False)
    score_id = Column("score_id", BigInteger, nullable=False)

    __table_args__ = (
        Index("first_place_scores_map_md5_mode_index", map_md5, mode),
        PrimaryKeyConstraint(map_md5, mode)
    )


READ_PARAMS = (
    FirstPlaceScoresTable.map_md5,
    FirstPlaceScoresTable.mode,
    FirstPlaceScoresTable.score_id
)


class FirstPlaceScore(TypedDict):
    map_md5: str
    mode: int
    score_id: int


async def create_or_update(
    map_md5: str,
    mode: int,
    score_id: int
) -> None:
    insert_stmt = mysql_insert(FirstPlaceScoresTable).values(
        map_md5=map_md5,
        mode=mode,
        score_id=score_id
    ).on_duplicate_key_update(
        score_id=score_id
    )
    print(insert_stmt)
    await app.state.services.database.execute(insert_stmt)


async def fetch_one(map_md5: str, mode: GameMode) -> FirstPlaceScore | None:
    select_stmt = select(*READ_PARAMS).where(and_(FirstPlaceScoresTable.map_md5 == map_md5, FirstPlaceScoresTable.mode == mode))
    score = await app.state.services.database.fetch_one(select_stmt)
    return cast(FirstPlaceScore | None, score)