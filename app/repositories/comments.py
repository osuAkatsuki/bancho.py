from __future__ import annotations

import textwrap
from enum import StrEnum
from typing import Any
from typing import cast
from typing import TypedDict

import app.state.services

# +-----------------+-----------------------------+------+-----+---------+----------------+
# | Field           | Type                        | Null | Key | Default | Extra          |
# +-----------------+-----------------------------+------+-----+---------+----------------+
# | id              | int                         | NO   | PRI | NULL    | auto_increment |
# | target_id       | int                         | NO   |     | NULL    |                |
# | target_type     | enum('replay','map','song') | NO   |     | NULL    |                |
# | userid          | int                         | NO   |     | NULL    |                |
# | time            | float(6,3)                  | NO   |     | NULL    |                |
# | comment         | varchar(80)                 | NO   |     | NULL    |                |
# | colour          | char(6)                     | YES  |     | NULL    |                |
# +-----------------+-----------------------------+------+-----+---------+----------------+

READ_PARAMS = textwrap.dedent(
    """\
        id, target_id, target_type, userid, time, comment, colour
    """,
)


class TargetType(StrEnum):
    REPLAY = "replay"
    BEATMAP = "map"
    SONG = "song"


class Comment(TypedDict):
    id: int
    target_id: int
    target_type: TargetType
    userid: int
    time: float
    comment: str
    colour: str


class CommentUpdateFields(TypedDict, total=False):
    target_id: int
    target_type: TargetType
    userid: int
    time: float
    comment: str
    colour: str


async def create(
    target_id: int,
    target_type: TargetType,
    userid: int,
    time: float,
    comment: str,
    colour: str,
) -> Comment:
    """Create a new comment entry in the database."""
    query = f"""\
        INSERT INTO comments (target_id, target_type, userid, time, comment, colour)
             VALUES (:target_id, :target_type, :userid, :time, :comment, :colour)
    """
    params = {
        "target_id": target_id,
        "target_type": target_type,
        "userid": userid,
        "time": time,
        "comment": comment,
        "colour": colour,
    }
    rec_id = await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM comments
         WHERE id = :id
    """
    params = {
        "id": rec_id,
    }
    _comment = await app.state.services.database.fetch_one(query, params)

    assert _comment is not None
    return cast(Comment, dict(_comment._mapping))


async def fetch_count(
    target_id: int | None = None,
    target_type: TargetType | None = None,
    userid: int | None = None,
    time: float | None = None,
    comment: str | None = None,
    colour: str | None = None,
) -> int:
    """Fetch the number of comments in the database."""
    query = """\
        SELECT COUNT(*) AS count
          FROM comments
        WHERE target_id = COALESCE(:target_id, target_id)
          AND target_type = COALESCE(:target_type, target_type)
          AND userid = COALESCE(:userid, userid)
          AND time = COALESCE(:time, time)
          AND comment = COALESCE(:comment, comment)
          AND colour = COALESCE(:colour, colour)
    """
    params: dict[str, Any] = {
        "server": target_id,
        "set_id": target_type,
        "status": userid,
        "artist": time,
        "creator": comment,
        "filename": colour,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    assert rec is not None
    return cast(int, rec._mapping["count"])


async def fetch_all(
    score_id: int | None = None,
    map_set_id: int | None = None,
    map_id: int | None = None,
) -> list[Comment]:
    """Fetch a list of comments from the database."""
    query = f"""\
        SELECT c.time, c.target_type, c.colour, c.comment, u.priv
          FROM comments c
         INNER JOIN users u ON u.id = c.userid
         WHERE (c.target_type = 'replay' AND c.target_id = :score_id)
         OR (c.target_type = 'song' AND c.target_id = :map_set_id)
         OR (c.target_type = 'map' AND c.target_id = :map_id)
    """
    params: dict[str, Any] = {
        "score_id": score_id,
        "map_set_id": map_set_id,
        "map_id": map_id,
    }

    comments = await app.state.services.database.fetch_all(query, params)
    return cast(list[Comment], [dict(c._mapping) for c in comments])
