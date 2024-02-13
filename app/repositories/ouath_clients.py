from __future__ import annotations

import textwrap
from typing import TypedDict
from typing import cast

import app.state.services

# +--------------+-------------+------+-----+---------+----------------+
# | Field        | Type        | Null | Key | Default | Extra          |
# +--------------+-------------+------+-----+---------+----------------+
# | id           | varchar(64) | NO   | PRI | NULL    | auto_increment |
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


class OAuthClient(TypedDict):
    id: int
    name: str | None
    secret: str
    owner: int
    redirect_uri: str | None


async def create(
    secret: str,
    owner: int,
    name: str | None = None,
    redirect_uri: str | None = None,
) -> OAuthClient:
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
    return cast(OAuthClient, dict(rec._mapping))


async def fetch_one(id: str) -> OAuthClient | None:
    """Fetch a signle client from the database."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM oauth_clients
         WHERE id = :id
    """
    params = {
        "id": id,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    return cast(OAuthClient, dict(rec._mapping)) if rec is not None else None


async def fetch_many(
    owner: int | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[OAuthClient]:
    """Fetch all clients from the database."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM oauth_clients
         WHERE owner = COALESCE(:owner, owner)
    """
    params = {
        "owner": owner,
    }
    if page is not None and page_size is not None:
        query += """\
            LIMIT :limit
           OFFSET :offset
        """
        params["limit"] = page_size
        params["offset"] = (page - 1) * page_size

    recs = await app.state.services.database.fetch_all(query, params)
    return cast(list[OAuthClient], [dict(rec._mapping) for rec in recs])


async def update(
    id: int,
    secret: str | None = None,
    owner: int | None = None,
    name: str | None = None,
    redirect_uri: str | None = None,
) -> OAuthClient | None:
    """Update an existing client in the database."""
    query = """\
        UPDATE oauth_clients
           SET secret = COALESCE(:secret, secret),
               owner = COALESCE(:owner, owner),
               redirect_uri = COALESCE(:redirect_uri, redirect_uri),
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
    return cast(OAuthClient, dict(rec._mapping)) if rec is not None else None
