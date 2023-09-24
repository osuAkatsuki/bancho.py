from __future__ import annotations

import textwrap
from typing import Any
from typing import Optional

import app.state.services

# +--------------+------------------------+------+-----+---------+-------+
# | Field        | Type                   | Null | Key | Default | Extra |
# +--------------+------------------------+------+-----+---------+-------+
# | id           | int                    | NO   | PRI | NULL    |       |
# | from_id      | int                    | NO   |     | NULL    |       |
# | to_id        | int                    | NO   |     | NULL    |       |
# | msg          | varchar(2048)          | NO   |     | NULL    |       |
# | time         | int                    | YES  |     | NULL    |       |
# | read         | tinyint(1)             | NO   |     | NULL    |       |
# +--------------+------------------------+------+-----+---------+-------+

READ_PARAMS = textwrap.dedent(
    """\
        id, from_id, to_id, msg, time, `read`
    """,
)


async def create(from_id: int, to_id: int, msg: str) -> dict[str, Any]:
    """Create a new mail entry in the database."""
    query = f"""\
        INSERT INTO mail (from_id, to_id, msg, time)
             VALUES (:from_id, :to_id, :msg, UNIX_TIMESTAMP())
    """
    params = {"from_id": from_id, "to_id": to_id, "msg": msg}
    rec_id = await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM mail
         WHERE id = :id
    """
    params = {
        "id": rec_id,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    assert rec is not None
    return dict(rec)


async def fetch_one(
    from_id: int | None = None,
    to_id: int | None = None,
    time: str | None = None,
    read: bool | None = None,
) -> dict[str, Any] | None:
    """Fetch a mail entry from the database."""
    if from_id is None and to_id is None and time is None and read is None:
        raise ValueError("Must provide at least one parameter.")

    query = f"""\
        SELECT {READ_PARAMS}
          FROM mail
         WHERE from_id = COALESCE(:from_id, from_id)
           AND to_id = COALESCE(:to_id, to_id)
           AND time = COALESCE(:time, time)
           AND read = COALESCE(:read, read)
    """
    params = {
        "from_id": from_id,
        "to_id": to_id,
        "time": time,
        "read": read,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    return dict(rec) if rec is not None else None


async def fetch_count(
    from_id: int | None = None,
    to_id: int | None = None,
    time: str | None = None,
    read: bool | None = None,
) -> int:
    """Fetch the number of mails in the database."""
    query = """\
        SELECT COUNT(*) AS count
          FROM mail
        WHERE from_id = COALESCE(:from_id, from_id)
          AND to_id = COALESCE(:to_id, to_id)
          AND time = COALESCE(:time, time)
          AND `read` = COALESCE(:read, read)
    """
    params = {
        "from_id": from_id,
        "to_id": to_id,
        "time": time,
        "read": read,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    assert rec is not None
    return rec["count"]


async def fetch_all(
    to_id: int,
    read: bool,
) -> list[dict[str, Any]]:
    """Fetch a list of mails from the database."""
    query = f"""\
        SELECT m.`msg`, m.`time`, m.`from_id`,
         (SELECT name FROM users WHERE id = m.`from_id`) AS `from`,
         (SELECT name FROM users WHERE id = m.`to_id`) AS `to`
          FROM `mail` m
         WHERE m.`to_id` = :to_id
           AND m.`read` = :read
    """
    params = {
        "to_id": to_id,
        "read": read,
    }

    recs = await app.state.services.database.fetch_all(query, params)
    return [dict(rec) for rec in recs]


async def update(
    to_id: int,
    from_id: int,
    read_from: bool | None = None,
    read_to: bool | None = None,
) -> dict[str, Any] | None:
    """Update a mail entry in the database."""
    query = """\
        UPDATE mail
           SET `read` = :read_to
         WHERE to_id = :to_id
            AND from_id = :from_id
            AND `read` = :read_from
    """
    params = {
        "to_id": to_id,
        "from_id": from_id,
        "read_from": read_from,
        "read_to": read_to,
    }

    rec_id = await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM mail
        WHERE id = :id
    """
    params = {
        "id": rec_id,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    return dict(rec) if rec is not None else None


async def delete(id: int) -> dict[str, Any] | None:
    """Delete a mail entry from the database."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM mail
        WHERE id = :id
    """
    params = {
        "id": id,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    if rec is None:
        return None

    query = """\
        DELETE FROM mail
              WHERE id = :id
    """
    params = {
        "id": id,
    }
    await app.state.services.database.execute(query, params)
    return dict(rec)
