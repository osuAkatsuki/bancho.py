from __future__ import annotations

import textwrap
from typing import Any
from typing import Optional

import app.state.services

# +------------+--------------+------+-----+---------+----------------+
# | Field      | Type         | Null | Key | Default | Extra          |
# +------------+--------------+------+-----+---------+----------------+
# | id         | int          | NO   | PRI | NULL    | auto_increment |
# | name       | varchar(32)  | NO   | UNI | NULL    |                |
# | topic      | varchar(256) | NO   |     | NULL    |                |
# | read_priv  | int          | NO   |     | 1       |                |
# | write_priv | int          | NO   |     | 2       |                |
# | auto_join  | tinyint(1)   | NO   |     | 0       |                |
# +------------+--------------+------+-----+---------+----------------+

READ_PARAMS = textwrap.dedent(
    """\
        id, name, topic, read_priv, write_priv, auto_join
    """,
)


async def create(
    name: str,
    topic: str,
    read_priv: int,
    write_priv: int,
    auto_join: bool,
) -> dict[str, Any]:
    """Create a new channel."""
    query = """\
        INSERT INTO channels (name, topic, read_priv, write_priv, auto_join)
             VALUES (:name, :topic, :read_priv, :write_priv, :auto_join)

    """
    params = {
        "name": name,
        "topic": topic,
        "read_priv": read_priv,
        "write_priv": write_priv,
        "auto_join": auto_join,
    }
    rec_id = await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM channels
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
    """Fetch a single channel."""
    if id is None and name is None:
        raise ValueError("Must provide at least one parameter.")
    query = f"""\
        SELECT {READ_PARAMS}
          FROM channels
         WHERE id = COALESCE(:id, id)
           AND name = COALESCE(:name, name)
    """
    params = {
        "id": id,
        "name": name,
    }

    rec = await app.state.services.database.fetch_one(query, params)
    return dict(rec) if rec is not None else None


async def fetch_count(
    read_priv: Optional[int] = None,
    write_priv: Optional[int] = None,
    auto_join: Optional[bool] = None,
) -> int:
    if read_priv is None and write_priv is None and auto_join is None:
        raise ValueError("Must provide at least one parameter.")

    query = """\
        SELECT COUNT(*) AS count
          FROM channels
         WHERE read_priv = COALESCE(:read_priv, read_priv)
           AND write_priv = COALESCE(:write_priv, write_priv)
           AND auto_join = COALESCE(:auto_join, auto_join)
    """
    params = {
        "read_priv": read_priv,
        "write_priv": write_priv,
        "auto_join": auto_join,
    }

    rec = await app.state.services.database.fetch_one(query, params)
    assert rec is not None
    return rec["count"]


async def fetch_many(
    read_priv: Optional[int] = None,
    write_priv: Optional[int] = None,
    auto_join: Optional[bool] = None,
    page: Optional[int] = None,
    page_size: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Fetch multiple channels from the database."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM channels
         WHERE read_priv = COALESCE(:read_priv, read_priv)
           AND write_priv = COALESCE(:write_priv, write_priv)
           AND auto_join = COALESCE(:auto_join, auto_join)
    """
    params = {
        "read_priv": read_priv,
        "write_priv": write_priv,
        "auto_join": auto_join,
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
    name: str,
    topic: Optional[str] = None,
    read_priv: Optional[int] = None,
    write_priv: Optional[int] = None,
    auto_join: Optional[bool] = None,
) -> Optional[dict[str, Any]]:
    """Update a channel in the database."""
    query = """\
        UPDATE channels
           SET topic = COALESCE(:topic, topic),
               read_priv = COALESCE(:read_priv, read_priv),
               write_priv = COALESCE(:write_priv, write_priv),
               auto_join = COALESCE(:auto_join, auto_join)
         WHERE name = :name
    """
    params = {
        "name": name,
        "topic": topic,
        "read_priv": read_priv,
        "write_priv": write_priv,
        "auto_join": auto_join,
    }
    await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM channels
         WHERE name = :name
    """
    params = {
        "name": name,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    return dict(rec) if rec is not None else None


async def delete(
    name: str,
) -> Optional[dict[str, Any]]:
    """Delete a channel from the database."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM channels
         WHERE name = :name
    """
    params = {
        "name": name,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    if rec is None:
        return None

    query = """\
        DELETE FROM channels
              WHERE name = :name
    """
    params = {
        "name": name,
    }
    await app.state.services.database.execute(query, params)
    return dict(rec)
