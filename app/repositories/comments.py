from __future__ import annotations

import textwrap
from typing import Any
from typing import Optional

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


async def create(
    target_id: int,
    target_type: str,
    userid: int,
    time: float,
    comment: str,
    colour: str,
) -> dict[str, Any]:
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
    rec = await app.state.services.database.fetch_one(query, params)
    assert rec is not None
    return dict(rec)


async def fetch_one(
    target_id: int | None = None,
    target_type: str | None = None,
    userid: int | None = None,
    colour: str | None = None,
) -> dict[str, Any] | None:
    """Fetch a comment entry from the database."""
    if target_id is None and target_type is None and userid is None and colour is None:
        raise ValueError("Must provide at least one parameter.")

    query = f"""
        SELECT {READ_PARAMS}
          FROM comments
         WHERE target_id = COALESCE(:target_id, target_id)
           AND target_type = COALESCE(:target_type, target_type)
           AND userid = COALESCE(:userid, userid)
           AND colour = COALESCE(:colour, colour)
    """
    params = {
        "target_id": target_id,
        "target_type": target_type,
        "userid": userid,
        "colour": colour,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    return dict(rec) if rec is not None else None


async def fetch_count(
    target_id: int | None = None,
    target_type: str | None = None,
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
    params = {
        "server": target_id,
        "set_id": target_type,
        "status": userid,
        "artist": time,
        "creator": comment,
        "filename": colour,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    assert rec is not None
    return rec["count"]


async def fetch_all(
    score_id: int | None = None,
    map_set_id: int | None = None,
    map_id: int | None = None,
) -> list[dict[str, Any]]:
    """Fetch a list of comments from the database."""
    query = f"""\
        SELECT c.time, c.target_type, c.colour, c.comment, u.priv
          FROM comments c
         INNER JOIN users u ON u.id = c.userid
         WHERE (c.target_type = 'replay' AND c.target_id = :score_id)
         OR (c.target_type = 'song' AND c.target_id = :map_set_id)
         OR (c.target_type = 'map' AND c.target_id = :map_id)
    """
    params = {
        "score_id": score_id,
        "map_set_id": map_set_id,
        "map_id": map_id,
    }

    recs = await app.state.services.database.fetch_all(query, params)
    return [dict(rec) for rec in recs]


async def update(
    id: int,
    target_id: int | None = None,
    target_type: str | None = None,
    userid: int | None = None,
    time: float | None = None,
    comment: str | None = None,
    colour: str | None = None,
) -> dict[str, Any] | None:
    """Update a comment entry in the database."""
    query = """\
        UPDATE comments
           SET target_id = COALESCE(:target_id, target_id)
               target_type = COALESCE(:target_type, target_type)
               userid = COALESCE(:user_id, userid)
               time = COALESCE(:time, time)
               comment = COALESCE(:comment, comment)
               colour = COALESCE(:colour, colour)
         WHERE id = :id
    """
    params = {
        "id": id,
        "target_id": target_id,
        "target_type": target_type,
        "userid": userid,
        "time": time,
        "comment": comment,
        "colour": colour,
    }
    await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM comments
        WHERE id = :id
    """
    params = {
        "id": id,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    return dict(rec) if rec is not None else None


async def delete(id: int) -> dict[str, Any] | None:
    """Delete a comment entry from the database."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM comments
        WHERE id = :id
    """
    params = {
        "id": id,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    if rec is None:
        return None

    query = """\
        DELETE FROM comments
              WHERE id = :id
    """
    params = {
        "id": id,
    }
    await app.state.services.database.execute(query, params)
    return dict(rec)
