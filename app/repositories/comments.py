from __future__ import annotations

import textwrap
from enum import StrEnum
from typing import Any
from typing import TypedDict
from typing import cast

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
        c.id, c.target_id, c.target_type, c.userid, c.time, c.comment, c.colour
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
    query = f"""\
        INSERT INTO comments (target_id, target_type, userid, time, comment, colour)
             VALUES (:target_id, :target_type, :userid, :time, :comment, :colour)
    """
    params: dict[str, Any] = {
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
          FROM comments c
         WHERE id = :id
    """
    params = {
        "id": rec_id,
    }
    _comment = await app.state.services.database.fetch_one(query, params)

    assert _comment is not None
    return cast(Comment, dict(_comment._mapping))


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
    query = f"""\
        SELECT {READ_PARAMS}, u.priv
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
    return cast(list[CommentWithUserPrivileges], [dict(c._mapping) for c in comments])
