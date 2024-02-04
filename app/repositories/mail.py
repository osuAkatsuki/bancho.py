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


class MailWithUsernames(Mail):
    from_name: str
    to_name: str


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


async def fetch_all_for_user(
    user_id: int,
    read: bool | None = None,
) -> list[MailWithUsernames]:
    """Fetch all of mail to a given target from the database."""
    query = f"""\
        SELECT {READ_PARAMS},
         (SELECT name FROM users WHERE id = m.`from_id`) AS `from_name`,
         (SELECT name FROM users WHERE id = m.`to_id`) AS `to_name`
          FROM `mail` m
         WHERE m.`to_id` = :to_id
           AND m.`read` = COALESCE(:read, `read`)
    """
    params = {
        "to_id": user_id,
        "read": read,
    }

    mail = await app.state.services.database.fetch_all(query, params)
    return cast(list[MailWithUsernames], [dict(m._mapping) for m in mail])


async def mark_conversation_as_read(
    to_id: int,
    from_id: int,
) -> list[Mail]:
    """Mark any unread mail for a given player from a given player as read."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM mail
        WHERE to_id = :to_id
          AND from_id = :from_id
          AND `read` = False
    """
    params = {
        "to_id": to_id,
        "from_id": from_id,
    }
    all_mail = await app.state.services.database.fetch_all(query, params)
    if not all_mail:
        return []

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

    return cast(list[Mail], [dict(mail._mapping) for mail in all_mail])
