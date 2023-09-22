from __future__ import annotations

import textwrap
from typing import Any
from typing import cast
from typing import Optional
from typing import TypedDict

import app.state.services
from app._typing import UNSET
from app._typing import Unset

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


class Clan(TypedDict):
    id: int
    name: str
    tag: str
    owner: int
    created_at: str


class ClanUpdateFields(TypedDict, total=False):
    name: str
    tag: str
    owner: int


async def create(
    name: str,
    tag: str,
    owner: int,
) -> Clan:
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
    clan = await app.state.services.database.fetch_one(query, params)

    assert clan is not None
    return cast(Clan, clan)


async def fetch_one(
    id: int | None = None,
    name: str | None = None,
    tag: str | None = None,
    owner: int | None = None,
) -> Clan | None:
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
    clan = await app.state.services.database.fetch_one(query, params)

    return cast(Clan, clan) if clan is not None else None


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
    page: int | None = None,
    page_size: int | None = None,
) -> list[Clan]:
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

    clan = await app.state.services.database.fetch_all(query, params)
    return cast(list[Clan], clan)


async def update(
    id: int,
    name: str | Unset = UNSET,
    tag: str | Unset = UNSET,
    owner: int | Unset = UNSET,
) -> Clan | None:
    """Update a clan in the database."""
    update_fields: ClanUpdateFields = {}
    if not isinstance(name, Unset):
        update_fields["name"] = name
    if not isinstance(tag, Unset):
        update_fields["tag"] = tag
    if not isinstance(owner, Unset):
        update_fields["owner"] = owner

    query = f"""\
        UPDATE clans
           SET {",".join(f"{k} = :{k}" for k in update_fields)}
         WHERE id = :id
    """
    values = {"id": id} | update_fields
    await app.state.services.database.execute(query, values)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM clans
         WHERE id = :id
    """
    params = {
        "id": id,
    }
    clan = await app.state.services.database.fetch_one(query, params)
    return cast(Clan, clan) if clan is not None else None


async def delete(id: int) -> Clan | None:
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
    clan = await app.state.services.database.execute(query, params)
    return cast(Clan, clan) if clan is not None else None
