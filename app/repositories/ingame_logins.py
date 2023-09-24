from __future__ import annotations

import textwrap
from datetime import datetime
from typing import cast
from typing import TypedDict

import app.state.services
from app._typing import _UnsetSentinel
from app._typing import UNSET

# +--------------+------------------------+------+-----+---------+-------+
# | Field        | Type                   | Null | Key | Default | Extra |
# +--------------+------------------------+------+-----+---------+-------+
# | id           | int                    | NO   | PRI | NULL    |       |
# | userid       | int                    | NO   |     | NULL    |       |
# | ip           | varchar(45)            | NO   |     | NULL    |       |
# | osu_ver      | date                   | NO   |     | NULL    |       |
# | osu_stream   | varchar(11)            | NO   |     | NULL    |       |
# | datetime     | datetime               | NO   |     | NULL    |       |
# +--------------+------------------------+------+-----+---------+-------+

READ_PARAMS = textwrap.dedent(
    """\
        id, userid, ip, osu_ver, osu_stream, datetime
    """,
)


class IngameLogin(TypedDict):
    id: int
    userid: str
    ip: str
    osu_ver: str
    osu_stream: str
    datetime: datetime


class InGameLoginUpdateFields(TypedDict, total=False):
    userid: str
    ip: str
    osu_ver: str
    osu_stream: str


async def create(
    user_id: int,
    ip: str,
    osu_ver: str,
    osu_stream: str,
) -> IngameLogin:
    """Create a new login entry in the database."""
    query = f"""\
        INSERT INTO ingame_logins (userid, ip, osu_ver, osu_stream, datetime)
             VALUES (:userid, :ip, :osu_ver, :osu_stream, NOW())
    """
    params = {
        "userid": user_id,
        "ip": ip,
        "osu_ver": osu_ver,
        "osu_stream": osu_stream,
    }
    rec_id = await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM ingame_logins
         WHERE id = :id
    """
    params = {
        "id": rec_id,
    }
    ingame_login = await app.state.services.database.fetch_one(query, params)

    assert ingame_login is not None
    return cast(IngameLogin, dict(ingame_login._mapping))


async def fetch_one(
    id: int | None = None,
) -> IngameLogin | None:
    """Fetch a login entry from the database."""
    if id is None:
        raise ValueError("Must provide at least one parameter.")

    query = f"""\
        SELECT {READ_PARAMS}
          FROM ingame_logins
         WHERE id = COALESCE(:id, id)
    """
    params = {
        "id": id,
    }
    ingame_login = await app.state.services.database.fetch_one(query, params)

    return cast(IngameLogin, ingame_login) if ingame_login is not None else None


async def fetch_count(
    user_id: int | None = None,
    ip: str | None = None,
) -> int:
    """Fetch the number of logins in the database."""
    query = """\
        SELECT COUNT(*) AS count
          FROM ingame_logins
        WHERE userid = COALESCE(:userid, userid)
          AND ip = COALESCE(:ip, ip)
    """
    params = {
        "userid": user_id,
        "ip": ip,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    assert rec is not None
    return cast(int, rec._mapping["count"])


async def fetch_many(
    user_id: int | None = None,
    ip: str | None = None,
    osu_ver: str | None = None,
    osu_stream: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[IngameLogin]:
    """Fetch a list of logins from the database."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM ingame_logins
         WHERE userid = COALESCE(:userid, userid)
           AND ip = COALESCE(:ip, ip)
           AND osu_ver = COALESCE(:osu_ver, osu_ver)
           AND osu_stream = COALESCE(:osu_stream, osu_stream)
    """
    params = {
        "userid": user_id,
        "ip": ip,
        "osu_ver": osu_ver,
        "osu_stream": osu_stream,
    }

    if page is not None and page_size is not None:
        query += """\
            LIMIT :limit
           OFFSET :offset
        """
        params["limit"] = page_size
        params["offset"] = (page - 1) * page_size

    ingame_logins = await app.state.services.database.fetch_all(query, params)
    return cast(list[IngameLogin], ingame_logins)
