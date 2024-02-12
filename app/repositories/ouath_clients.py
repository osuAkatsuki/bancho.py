from __future__ import annotations

import textwrap
from typing import Any
from typing import Optional

import app.state.services

# +--------------+-------------+------+-----+---------+----------------+
# | Field        | Type        | Null | Key | Default | Extra          |
# +--------------+-------------+------+-----+---------+----------------+
# | id           | int         | NO   | PRI | NULL    | auto_increment |
# | name         | varchar(16) | YES  |     | NULL    |                |
# | secret       | varchar(32) | NO   |     | NULL    |                |
# | owner        | int         | NO   |     | NULL    |                |
# | redirect_uri | text        | YES  |     | NULL    |                |
# +--------------+-------------+------+-----+---------+----------------+

READ_PARAMS = textwrap.dedent(
    """\
        id, name, secret, owner, redirect_uri
    """,
)


async def create(
    secret: str,
    owner: int,
    name: str | None = None,
    redirect_uri: str | None = None,
) -> dict[str, Any]:
    """Create a new client in the database."""
    query = """\
        INSERT INTO oauth_clients (secret, owner, name, redirect_uri)
             VALUES (:secret, :owner, :name, :redirect_uri)
    """
    params = {
        "secret": secret,
        "owner": owner,
        "name": name,
        "redirect_uri": redirect_uri,
    }
    rec_id = await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM oauth_clients
         WHERE id = :id
    """
    params = {
        "id": rec_id,
    }

    rec = await app.state.services.database.fetch_one(query, params)
    assert rec is not None
    return dict(rec)


async def fetch_one(
    id: int | None = None,
    owner: int | None = None,
    secret: str | None = None,
    name: str | None = None,
) -> dict[str, Any] | None:
    """Fetch a signle client from the database."""
    if id is None and owner is None and secret is None:
        raise ValueError("Must provide at least one parameter.")

    query = f"""\
        SELECT {READ_PARAMS}
          FROM oauth_clients
         WHERE id = COALESCE(:id, id)
            AND owner = COALESCE(:owner, owner)
            AND secret = COALESCE(:secret, secret)
            AND name = COALESCE(:name, name)
    """
    params = {
        "id": id,
        "owner": owner,
        "secret": secret,
        "name": name,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    return dict(rec) if rec is not None else None


async def fetch_many(
    id: int | None = None,
    owner: int | None = None,
    secret: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[dict[str, Any]] | None:
    """Fetch all clients from the database."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM oauth_clients
         WHERE id = COALESCE(:id, id)
            AND owner = COALESCE(:owner, owner)
            AND secret = COALESCE(:secret, secret)
    """
    params = {
        "id": id,
        "owner": owner,
        "secret": secret,
    }

    if page is not None and page_size is not None:
        query += """\
            LIMIT :limit
           OFFSET :offset
        """
        params["limit"] = page_size
        params["offset"] = (page - 1) * page_size

    rec = await app.state.services.database.fetch_one(query, params)
    return dict(rec) if rec is not None else None


async def update(
    id: int,
    secret: str | None = None,
    owner: int | None = None,
    name: str | None = None,
    redirect_uri: str | None = None,
) -> dict[str, Any] | None:
    """Update an existing client in the database."""
    query = """\
        UPDATE oauth_clients
           SET secret = COALESCE(:secret, secret),
               owner = COALESCE(:owner, owner),
               redirect_uri = COALESCE(:redirect_uri, redirect_uri)
               name = COALESCE(:name, name)
         WHERE id = :id
    """
    params = {
        "id": id,
        "secret": secret,
        "owner": owner,
        "name": name,
        "redirect_uri": redirect_uri,
    }
    await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM oauth_clients
         WHERE id = :id
    """
    params = {
        "id": id,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    return dict(rec) if rec is not None else None
