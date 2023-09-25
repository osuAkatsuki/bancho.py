from __future__ import annotations

import textwrap
from typing import cast
from typing import TypedDict

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


class Mail(TypedDict):
    id: int
    from_id: int
    to_id: int
    msg: str
    time: int
    read: bool


READ_PARAMS = textwrap.dedent(
    """\
        id, from_id, to_id, msg, time, `read`
    """,
)


async def create(from_id: int, to_id: int, msg: str) -> Mail:
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
    mail = await app.state.services.database.fetch_one(query, params)

    assert mail is not None
    return cast(Mail, dict(mail._mapping))


async def fetch_all(to_id: int, read: bool) -> list[Mail]:
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

    mails = await app.state.services.database.fetch_all(query, params)
    return cast(list[Mail], [dict(m._mapping) for m in mails])


async def mark_as_read(
    to_id: int,
    from_id: int,
) -> Mail | None:
    """Update a mail entry in the database."""
    query = """\
        UPDATE mail
           SET `read` = True
         WHERE to_id = :to_id
            AND from_id = :from_id
            AND `read` = False
    """
    params = {
        "to_id": to_id,
        "from_id": from_id,
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
    mail = await app.state.services.database.fetch_one(query, params)
    return cast(Mail, dict(mail._mapping)) if mail is not None else None
