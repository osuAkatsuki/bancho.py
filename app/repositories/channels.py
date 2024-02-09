from __future__ import annotations

import textwrap
from typing import Any
from typing import cast
from typing import TypedDict

import app.state.services
from app._typing import _UnsetSentinel
from app._typing import UNSET

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


class Channel(TypedDict):
    id: int
    name: str
    topic: str
    read_priv: int
    write_priv: int
    auto_join: bool


class ChannelUpdateFields(TypedDict, total=False):
    name: str
    topic: str
    read_priv: int
    write_priv: int
    auto_join: bool


async def create(
    name: str,
    topic: str,
    read_priv: int,
    write_priv: int,
    auto_join: bool,
) -> Channel:
    """Create a new channel."""
    query = """\
        INSERT INTO channels (name, topic, read_priv, write_priv, auto_join)
             VALUES (:name, :topic, :read_priv, :write_priv, :auto_join)

    """
    params: dict[str, Any] = {
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

    channel = await app.state.services.database.fetch_one(query, params)

    assert channel is not None
    return cast(Channel, dict(channel._mapping))


async def fetch_one(
    id: int | None = None,
    name: str | None = None,
) -> Channel | None:
    """Fetch a single channel."""
    if id is None and name is None:
        raise ValueError("Must provide at least one parameter.")
    query = f"""\
        SELECT {READ_PARAMS}
          FROM channels
         WHERE id = COALESCE(:id, id)
           AND name = COALESCE(:name, name)
    """
    params: dict[str, Any] = {
        "id": id,
        "name": name,
    }
    channel = await app.state.services.database.fetch_one(query, params)

    return cast(Channel, dict(channel._mapping)) if channel is not None else None


async def fetch_count(
    read_priv: int | None = None,
    write_priv: int | None = None,
    auto_join: bool | None = None,
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
    params: dict[str, Any] = {
        "read_priv": read_priv,
        "write_priv": write_priv,
        "auto_join": auto_join,
    }

    rec = await app.state.services.database.fetch_one(query, params)
    assert rec is not None
    return cast(int, rec._mapping["count"])


async def fetch_many(
    read_priv: int | None = None,
    write_priv: int | None = None,
    auto_join: bool | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[Channel]:
    """Fetch multiple channels from the database."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM channels
         WHERE read_priv = COALESCE(:read_priv, read_priv)
           AND write_priv = COALESCE(:write_priv, write_priv)
           AND auto_join = COALESCE(:auto_join, auto_join)
    """
    params: dict[str, Any] = {
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

    channels = await app.state.services.database.fetch_all(query, params)
    return cast(list[Channel], [dict(c._mapping) for c in channels])


async def update(
    name: str,
    topic: str | _UnsetSentinel = UNSET,
    read_priv: int | _UnsetSentinel = UNSET,
    write_priv: int | _UnsetSentinel = UNSET,
    auto_join: bool | _UnsetSentinel = UNSET,
) -> Channel | None:
    """Update a channel in the database."""
    update_fields: ChannelUpdateFields = {}
    if not isinstance(topic, _UnsetSentinel):
        update_fields["topic"] = topic
    if not isinstance(read_priv, _UnsetSentinel):
        update_fields["read_priv"] = read_priv
    if not isinstance(write_priv, _UnsetSentinel):
        update_fields["write_priv"] = write_priv
    if not isinstance(auto_join, _UnsetSentinel):
        update_fields["auto_join"] = auto_join

    query = f"""\
        UPDATE channels
           SET {",".join(f"{k} = COALESCE(:{k}, {k})" for k in update_fields)}
         WHERE name = :name
    """
    params: dict[str, Any] = {
        "name": name,
    } | update_fields
    await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM channels
         WHERE name = :name
    """
    params = {
        "name": name,
    }
    channel = await app.state.services.database.fetch_one(query, params)
    return cast(Channel, dict(channel._mapping)) if channel is not None else None


async def delete(
    name: str,
) -> Channel | None:
    """Delete a channel from the database."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM channels
         WHERE name = :name
    """
    params: dict[str, Any] = {
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
    channel = await app.state.services.database.execute(query, params)
    return cast(Channel, dict(channel._mapping)) if channel is not None else None
