from __future__ import annotations

import textwrap
from typing import Any
from typing import Optional

import app.state.services

# +--------------+------------------------+------+-----+---------+-----------------------------+
# | Field        | Type                   | Null | Key | Default | Extra                       |
# +--------------+------------------------+------+-----+---------+-----------------------------+
# | id           | int                    | NO   | PRI | NULL    | auto_increment              |
# | from         | int                    | NO   |     | NULL    |                             |
# | to           | int                    | NO   |     | NULL    |                             |
# | action       | varchar(32)            | NO   |     | NULL    |                             |
# | msg          | varchar(2048)          | YES  |     | NULL    |                             |
# | time         | datetime               | NO   |     | NULL    | on update current_timestamp |
# +--------------+------------------------+------+-----+---------+-----------------------------+

READ_PARAMS = textwrap.dedent(
    """\
        id, from, to, action, msg, time
    """,
)


async def create(
    id: int,
    _from: int,
    to: int,
    action: str,
    msg: str,
    time: str,
) -> dict[str, Any]:
    """Create a new log entry in the database."""
    query = f"""\
        INSERT INTO logs (id, from, to, action, msg, time)
            VALUES (:id, :from, :to, :action, :msg, NOW())
    """
    params = {
        "id": id,
        "from": _from,
        "to": to,
        "action": action,
        "msg": msg,
        "time": time,
    }
    rec_id = await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM maps
         WHERE id = :id
    """
    params = {
        "id": rec_id,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    assert rec is not None
    return dict(rec)


async def fetch_one(
    id: Optional[int] = None,
    _from: Optional[int] = None,
    to: Optional[int] = None,
    action: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Fetch a log entry from the database."""
    if id is None:
        raise ValueError("Must provide at least one parameter.")

    query = f"""\
        SELECT {READ_PARAMS}
          FROM logs
         WHERE id = COALESCE(:id, id)
          AND from = COALESCE(:from, from)
          AND to = COALESCE(:to, to)
          AND action = COALESCE(:action, action)
    """
    params = {
        "id": id,
        "from": _from,
        "to": to,
        "action": action,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    return dict(rec) if rec is not None else None


async def fetch_count(
    id: Optional[int] = None,
    _from: Optional[int] = None,
    to: Optional[int] = None,
    action: Optional[str] = None,
    msg: Optional[str] = None,
    time: Optional[str] = None,
) -> int:
    """Fetch the number of logs in the database."""
    query = """\
        SELECT COUNT(*) AS count
          FROM logs
        WHERE id = COALESCE(:id, id)
          AND from = COALESCE(:from, from)
          AND to = COALESCE(:to, to)
          AND action = COALESCE(:action, action)
          AND msg = COALESCE(:msg, msg)
          AND time = COALESCE(:time, time)
    """
    params = {
        "id": id,
        "from": _from,
        "to": to,
        "action": action,
        "msg": msg,
        "time": time,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    assert rec is not None
    return rec["count"]


async def fetch_many(
    id: Optional[int] = None,
    _from: Optional[int] = None,
    to: Optional[int] = None,
    action: Optional[str] = None,
    msg: Optional[str] = None,
    time: Optional[str] = None,
    page: Optional[int] = None,
    page_size: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Fetch a list of logs from the database."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM logs
         WHERE id = COALESCE(:id, id)
           AND from = COALESCE(:from, from)
           AND to = COALESCE(:to, to)
           AND action = COALESCE(:action, action)
           AND msg = COALESCE(:msg, msg)
           AND time = COALESCE(:time, time)
    """
    params = {
        "id": id,
        "from": _from,
        "to": to,
        "action": action,
        "msg": msg,
        "time": time,
    }

    if page is not None and page_size is not None:
        query += """\
            LIMIT :limit
           OFFSET :offset
        """
        params["limit"] = page_size
        params["offset"] = (page - 1) * page_size

    recs = await app.state.services.database.fetch_all(query, params)
    return [dict(rec) for rec in recs]


async def update(
    id: int,
    _from: Optional[int] = None,
    to: Optional[int] = None,
    action: Optional[str] = None,
    msg: Optional[str] = None,
    time: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Update a log entry in the database."""
    query = """\
        UPDATE logs
           SET from = COALESCE(:from, from),
               to = COALESCE(:to, to),
               action = COALESCE(:action, action),
               msg = COALESCE(:msg, msg),
               time = COALESCE(:time, time)
         WHERE id = :id
    """
    params = {
        "id": id,
        "from": _from,
        "to": to,
        "action": action,
        "msg": msg,
        "time": time,
    }
    await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM logs
        WHERE id = :id
    """
    params = {
        "id": id,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    return dict(rec) if rec is not None else None


async def delete(id: int) -> Optional[dict[str, Any]]:
    """Delete a log entry from the database."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM logs
        WHERE id = :id
    """
    params = {
        "id": id,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    if rec is None:
        return None

    query = """\
        DELETE FROM logs
              WHERE id = :id
    """
    params = {
        "id": id,
    }
    await app.state.services.database.execute(query, params)
    return dict(rec)
