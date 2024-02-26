from __future__ import annotations

from enum import StrEnum
from typing import TypedDict
from typing import cast

from sqlalchemy import CHAR
from sqlalchemy import Column
from sqlalchemy import Enum
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import and_
from sqlalchemy import insert
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.dialects.mysql import FLOAT

import app.state.services
from app.repositories import Base
from app.repositories.users import UsersTable


class TargetType(StrEnum):
    REPLAY = "replay"
    BEATMAP = "map"
    SONG = "song"


class CommentsTable(Base):
    __tablename__ = "comments"

    id = Column("id", Integer, nullable=False, primary_key=True, autoincrement=True)
    target_id = Column("target_id", nullable=False)
    target_type = Column(Enum(TargetType, name="target_type"), nullable=False)
    userid = Column("userid", Integer, nullable=False)
    time = Column("time", FLOAT(precision=6, scale=3), nullable=False)
    comment = Column("comment", String(80, collation="utf8"), nullable=False)
    colour = Column("colour", CHAR(6), nullable=True)


READ_PARAMS = (
    CommentsTable.id,
    CommentsTable.target_id,
    CommentsTable.target_type,
    CommentsTable.userid,
    CommentsTable.time,
    CommentsTable.comment,
    CommentsTable.colour,
)


class Comment(TypedDict):
    id: int
    target_id: int
    target_type: TargetType
    userid: int
    time: float
    comment: str
    colour: str | None


async def create(
    target_id: int,
    target_type: TargetType,
    userid: int,
    time: float,
    comment: str,
    colour: str | None,
) -> Comment:
    """Create a new comment entry in the database."""
    insert_stmt = insert(CommentsTable).values(
        target_id=target_id,
        target_type=target_type,
        userid=userid,
        time=time,
        comment=comment,
        colour=colour,
    )
    rec_id = await app.state.services.database.execute(insert_stmt)

    select_stmt = select(*READ_PARAMS).where(CommentsTable.id == rec_id)
    _comment = await app.state.services.database.fetch_one(select_stmt)

    assert _comment is not None
    return cast(Comment, _comment)


class CommentWithUserPrivileges(Comment):
    priv: int


async def fetch_all_relevant_to_replay(
    score_id: int | None = None,
    map_set_id: int | None = None,
    map_id: int | None = None,
) -> list[CommentWithUserPrivileges]:
    """\
    Fetch all comments from the database where any of the following match:
        - `score_id`
        - `map_set_id`
        - `map_id`
    """
    select_stmt = (
        select(READ_PARAMS, UsersTable.priv)
        .join(UsersTable, CommentsTable.userid == UsersTable.id)
        .where(
            or_(
                and_(
                    CommentsTable.target_type == TargetType.REPLAY,
                    CommentsTable.target_id == score_id,
                ),
                and_(
                    CommentsTable.target_type == TargetType.SONG,
                    CommentsTable.target_id == map_set_id,
                ),
                and_(
                    CommentsTable.target_type == TargetType.BEATMAP,
                    CommentsTable.target_id == map_id,
                ),
            ),
        )
    )

    comments = await app.state.services.database.fetch_all(select_stmt)
    return cast(list[CommentWithUserPrivileges], comments)
