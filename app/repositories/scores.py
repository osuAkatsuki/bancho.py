from __future__ import annotations

import textwrap
from typing import Any
from typing import Optional

import app.state.services

# +-----------------+-----------------+------+-----+---------+----------------+
# | Field           | Type            | Null | Key | Default | Extra          |
# +-----------------+-----------------+------+-----+---------+----------------+
# | id              | bigint unsigned | NO   | PRI | NULL    | auto_increment |
# | map_md5         | char(32)        | NO   |     | NULL    |                |
# | score           | int             | NO   |     | NULL    |                |
# | pp              | float(7,3)      | NO   |     | NULL    |                |
# | acc             | float(6,3)      | NO   |     | NULL    |                |
# | max_combo       | int             | NO   |     | NULL    |                |
# | mods            | int             | NO   |     | NULL    |                |
# | n300            | int             | NO   |     | NULL    |                |
# | n100            | int             | NO   |     | NULL    |                |
# | n50             | int             | NO   |     | NULL    |                |
# | nmiss           | int             | NO   |     | NULL    |                |
# | ngeki           | int             | NO   |     | NULL    |                |
# | nkatu           | int             | NO   |     | NULL    |                |
# | grade           | varchar(2)      | NO   |     | N       |                |
# | status          | tinyint         | NO   |     | NULL    |                |
# | mode            | tinyint         | NO   |     | NULL    |                |
# | play_time       | datetime        | NO   |     | NULL    |                |
# | time_elapsed    | int             | NO   |     | NULL    |                |
# | client_flags    | int             | NO   |     | NULL    |                |
# | userid          | int             | NO   |     | NULL    |                |
# | perfect         | tinyint(1)      | NO   |     | NULL    |                |
# | online_checksum | char(32)        | NO   |     | NULL    |                |
# +-----------------+-----------------+------+-----+---------+----------------+

READ_PARAMS = textwrap.dedent(
    """\
        id, map_md5, score, pp, acc, max_combo, mods, n300, n100, n50, nmiss, ngeki, nkatu,
        grade, status, mode, play_time, time_elapsed, client_flags, userid, perfect, online_checksum
    """,
)


async def create(
    map_md5: str,
    score: int,
    pp: float,
    acc: float,
    max_combo: int,
    mods: int,
    n300: int,
    n100: int,
    n50: int,
    nmiss: int,
    ngeki: int,
    nkatu: int,
    grade: str,
    status: int,
    mode: int,
    play_time: str,
    time_elapsed: int,
    client_flags: int,
    user_id: int,
    perfect: int,
    online_checksum: str,
) -> dict[str, Any]:
    query = """\
        INSERT INTO scores (map_md5, score, pp, acc, max_combo, mods, n300,
                            n100, n50, nmiss, ngeki, nkatu, grade, status,
                            mode, play_time, time_elapsed, client_flags,
                            userid, perfect, online_checksum)
             VALUES (:map_md5, :score, :pp, :acc, :max_combo, :mods, :n300,
                     :n100, :n50, :nmiss, :ngeki, :nkatu, :grade, :status,
                     :mode, :play_time, :time_elapsed, :client_flags,
                     :userid, :perfect, :online_checksum)
    """
    params = {
        "map_md5": map_md5,
        "score": score,
        "pp": pp,
        "acc": acc,
        "max_combo": max_combo,
        "mods": mods,
        "n300": n300,
        "n100": n100,
        "n50": n50,
        "nmiss": nmiss,
        "ngeki": ngeki,
        "nkatu": nkatu,
        "grade": grade,
        "status": status,
        "mode": mode,
        "play_time": play_time,
        "time_elapsed": time_elapsed,
        "client_flags": client_flags,
        "userid": user_id,
        "perfect": perfect,
        "online_checksum": online_checksum,
    }
    rec_id = await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM scores
         WHERE id = :id
    """
    params = {"id": rec_id}
    rec = await app.state.services.database.fetch_one(query, params)
    assert rec is not None
    return dict(rec)


async def fetch_one(id: int) -> Optional[dict[str, Any]]:
    query = f"""\
        SELECT {READ_PARAMS}
          FROM scores
         WHERE id = :id
    """
    params = {"id": id}
    rec = await app.state.services.database.fetch_one(query, params)
    return dict(rec) if rec is not None else None


async def fetch_count(
    map_md5: Optional[str] = None,
    mods: Optional[int] = None,
    status: Optional[int] = None,
    mode: Optional[int] = None,
    user_id: Optional[int] = None,
) -> int:
    query = """\
        SELECT COUNT(*) AS count
          FROM scores
         WHERE map_md5 = COALESCE(:map_md5, map_md5)
           AND mods = COALESCE(:mods, mods)
           AND status = COALESCE(:status, status)
           AND mode = COALESCE(:mode, mode)
           AND userid = COALESCE(:userid, userid)
    """
    params = {
        "map_md5": map_md5,
        "mods": mods,
        "status": status,
        "mode": mode,
        "userid": user_id,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    assert rec is not None
    return rec["count"]


async def fetch_many(
    map_md5: Optional[str] = None,
    mods: Optional[int] = None,
    status: Optional[int] = None,
    mode: Optional[int] = None,
    user_id: Optional[int] = None,
    page: Optional[int] = None,
    page_size: Optional[int] = None,
) -> list[dict[str, Any]]:
    query = f"""\
        SELECT {READ_PARAMS}
          FROM scores
         WHERE map_md5 = COALESCE(:map_md5, map_md5)
           AND mods = COALESCE(:mods, mods)
           AND status = COALESCE(:status, status)
           AND mode = COALESCE(:mode, mode)
           AND userid = COALESCE(:userid, userid)
    """
    params = {
        "map_md5": map_md5,
        "mods": mods,
        "status": status,
        "mode": mode,
        "userid": user_id,
    }
    if page is not None and page_size is not None:
        query += """\
            LIMIT :page_size
           OFFSET :offset
        """
        params["page_size"] = page_size
        params["offset"] = (page - 1) * page_size

    recs = await app.state.services.database.fetch_all(query, params)
    return [dict(rec) for rec in recs]


async def update(
    id: int,
    pp: Optional[float] = None,
    status: Optional[int] = None,
) -> Optional[dict[str, Any]]:
    query = """\
        UPDATE scores
           SET pp = COALESCE(:pp, pp),
               status = COALESCE(:status, status)
         WHERE id = :id
    """
    params = {
        "id": id,
        "pp": pp,
        "status": status,
    }
    await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM scores
         WHERE id = :id
    """
    params = {"id": id}
    rec = await app.state.services.database.fetch_one(query, params)
    return dict(rec) if rec is not None else None


# TODO: delete
