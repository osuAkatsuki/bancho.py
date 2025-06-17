from __future__ import annotations

from enum import StrEnum
from typing import TypedDict
from typing import cast

from sqlalchemy import CHAR
from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import and_
from sqlalchemy import insert
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.dialects.mysql import ENUM
from sqlalchemy.dialects.mysql import VARCHAR

import app.state.services
from app.repositories import Base
from app.repositories.users import UsersTable


class TargetType(StrEnum):
    replay = "replay"
    map = "map"
    song = "song"


class CommentsTable(Base):
    __tablename__ = "comments"

    id = Column("id", Integer, nullable=False, primary_key=True, autoincrement=True)
    target_id = Column(
        "target_id",
        Integer,
        nullable=False,
        comment="replay, map, or set id",
    )
    target_type = Column(ENUM(TargetType), nullable=False)
    userid = Column("userid", Integer, nullable=False)
    time = Column("time", Integer, nullable=False)
    comment = Column(
        "comment",
        VARCHAR(charset="utf8mb3", collation="utf8mb3_general_ci", length=80),
        nullable=False,
    )
    colour = Column("colour", CHAR(6), nullable=True, comment="rgb hex string")


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
    target_type: str
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
                    CommentsTable.target_type == TargetType.replay,
                    CommentsTable.target_id == score_id,
                ),
                and_(
                    CommentsTable.target_type == TargetType.song,
                    CommentsTable.target_id == map_set_id,
                ),
                and_(
                    CommentsTable.target_type == TargetType.map,
                    CommentsTable.target_id == map_id,
                ),
            ),
        )
    )

    comments = await app.state.services.database.fetch_all(select_stmt)
    return cast(list[CommentWithUserPrivileges], comments)
