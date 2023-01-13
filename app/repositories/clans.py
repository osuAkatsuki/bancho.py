from __future__ import annotations

import textwrap
from typing import Any
from typing import Optional

import app.state.services

# +------------+-------------+------+-----+---------+----------------+
# | Field      | Type        | Null | Key | Default | Extra          |
# +------------+-------------+------+-----+---------+----------------+
# | id         | int         | NO   | PRI | NULL    | auto_increment |
# | name       | varchar(16) | NO   | UNI | NULL    |                |
# | tag        | varchar(6)  | NO   | UNI | NULL    |                |
# | owner      | int         | NO   | UNI | NULL    |                |
# | created_at | datetime    | NO   |     | NULL    |                |
# +------------+-------------+------+-----+---------+----------------+

READ_PARAMS = textwrap.dedent(
    """\
        id, name, tag, owner, created_at
    """,
)


async def create(
    name: str,
    tag: str,
    owner: int,
) -> dict[str, Any]:
    """Create a new clan in the database."""
    query = f"""\
        INSERT INTO clans (name, tag, owner, created_at)
             VALUES (:name, :tag, :owner, NOW())
    """
    params = {
        "name": name,
        "tag": tag,
        "owner": owner,
    }
    rec_id = await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM clans
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
    tag: Optional[str] = None,
    owner: Optional[int] = None,
) -> Optional[dict[str, Any]]:
    """Fetch a single clan from the database."""
    if id is None and name is None and tag is None and owner is None:
        raise ValueError("Must provide at least one parameter.")

    query = f"""\
        SELECT {READ_PARAMS}
          FROM clans
         WHERE id = COALESCE(:id, id)
           AND name = COALESCE(:name, name)
           AND tag = COALESCE(:tag, tag)
           AND owner = COALESCE(:owner, owner)
    """
    params = {"id": id, "name": name, "tag": tag, "owner": owner}
    rec = await app.state.services.database.fetch_one(query, params)
    return dict(rec) if rec is not None else None


async def fetch_count() -> int:
    """Fetch the number of clans in the database."""
    query = """\
        SELECT COUNT(*) AS count
          FROM clans
    """
    rec = await app.state.services.database.fetch_one(query)
    assert rec is not None
    return rec["count"]


async def fetch_many(
    page: Optional[int] = None,
    page_size: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Fetch many clans from the database."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM clans
    """
    params = {}

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
    name: Optional[str] = None,
    tag: Optional[str] = None,
    owner: Optional[int] = None,
) -> Optional[dict[str, Any]]:
    """Update a clan in the database."""
    query = """\
        UPDATE clans
           SET name = :name,
               tag = :tag,
               owner = :owner
         WHERE id = :id
    """
    params = {
        "id": id,
        "name": name,
        "tag": tag,
        "owner": owner,
    }

    await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM clans
         WHERE id = :id
    """
    params = {
        "id": id,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    return dict(rec) if rec is not None else None


async def delete(id: int) -> Optional[dict[str, Any]]:
    """Delete a clan from the database."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM clans
         WHERE id = :id
    """
    params = {
        "id": id,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    if rec is None:
        return None

    query = """\
        DELETE FROM clans
         WHERE id = :id
    """
    params = {
        "id": id,
    }
    await app.state.services.database.execute(query, params)
    return dict(rec)
