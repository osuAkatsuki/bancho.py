from __future__ import annotations

import textwrap
from datetime import datetime
from typing import Any
from typing import cast
from typing import TypedDict

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
        `id`, `from`, `to`, `action`, `msg`, `time`
    """,
)


class Log(TypedDict):
    id: int
    _from: int
    to: int
    action: str
    msg: str | None
    time: datetime


async def create(
    _from: int,
    to: int,
    action: str,
    msg: str,
) -> Log:
    """Create a new log entry in the database."""
    query = f"""\
        INSERT INTO logs (`from`, `to`, `action`, `msg`, `time`)
            VALUES (:from, :to, :action, :msg, NOW())
    """
    params: dict[str, Any] = {
        "from": _from,
        "to": to,
        "action": action,
        "msg": msg,
    }
    rec_id = await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM logs
         WHERE id = :id
    """
    params = {
        "id": rec_id,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    assert rec is not None
    return cast(Log, dict(rec._mapping))
