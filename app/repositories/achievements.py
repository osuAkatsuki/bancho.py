from __future__ import annotations

import textwrap
from typing import Any
from typing import Optional

import app.state.services

# +-------+--------------+------+-----+---------+----------------+
# | Field | Type         | Null | Key | Default | Extra          |
# +-------+--------------+------+-----+---------+----------------+
# | id    | int          | NO   | PRI | NULL    | auto_increment |
# | file  | varchar(128) | NO   | UNI | NULL    |                |
# | name  | varchar(128) | NO   | UNI | NULL    |                |
# | desc  | varchar(256) | NO   | UNI | NULL    |                |
# | cond  | varchar(64)  | NO   |     | NULL    |                |
# +-------+--------------+------+-----+---------+----------------+

READ_PARAMS = textwrap.dedent(
    """\
        id, file, name, `desc`, cond
    """,
)


async def create(
    file: str,
    name: str,
    desc: str,
    cond: str,
) -> dict[str, Any]:
    """Create a new achievement."""
    query = """\
        INSERT INTO achievements (file, name, desc, cond)
             VALUES (:file, :name, :desc, :cond)
    """
    params = {
        "file": file,
        "name": name,
        "desc": desc,
        "cond": cond,
    }
    rec_id = await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM achievements
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
    name: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Fetch a single achievement."""
    if id is None and name is None:
        raise ValueError("Must provide at least one parameter.")

    query = f"""\
        SELECT {READ_PARAMS}
          FROM achievements
         WHERE id = COALESCE(:id, id)
            OR name = COALESCE(:name, name)
    """
    params = {
        "id": id,
        "name": name,
    }

    rec = await app.state.services.database.fetch_one(query, params)
    return dict(rec) if rec is not None else None


async def fetch_count() -> int:
    """Fetch the number of achievements."""
    query = """\
        SELECT COUNT(*) AS count
          FROM achievements
    """
    params = {}

    rec = await app.state.services.database.fetch_one(query, params)
    assert rec is not None
    return rec["count"]


async def fetch_many(
    page: Optional[int] = None,
    page_size: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Fetch a list of achievements."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM achievements
    """
    params = {}

    if page is not None and page_size is not None:
        query += """\
            LIMIT :limit
           OFFSET :offset
        """
        params["page_size"] = page_size
        params["offset"] = (page - 1) * page_size

    recs = await app.state.services.database.fetch_all(query, params)
    return [dict(rec) for rec in recs]


async def update(
    id: int,
    file: Optional[str] = None,
    name: Optional[str] = None,
    desc: Optional[str] = None,
    cond: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Update an existing achievement."""
    query = """\
        UPDATE achievements
           SET file = COALESCE(:file, file),
               name = COALESCE(:name, name),
               desc = COALESCE(:desc, desc),
               cond = COALESCE(:cond, cond)
         WHERE id = :id
    """
    params = {
        "id": id,
        "file": file,
        "name": name,
        "desc": desc,
        "cond": cond,
    }
    await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM achievements
         WHERE id = :id
    """
    params = {
        "id": id,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    return dict(rec) if rec is not None else None


async def delete(
    id: int,
) -> Optional[dict[str, Any]]:
    """Delete an existing achievement."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM achievements
         WHERE id = :id
    """
    params = {
        "id": id,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    if rec is None:
        return None

    query = """\
        DELETE FROM achievements
              WHERE id = :id
    """
    params = {
        "id": id,
    }
    await app.state.services.database.execute(query, params)
    return dict(rec)
