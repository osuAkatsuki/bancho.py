from __future__ import annotations

import textwrap
from typing import Any
from typing import Optional

import app.state.services
from app.utils import make_safe_name

# +-------------------+---------------+------+-----+---------+----------------+
# | Field             | Type          | Null | Key | Default | Extra          |
# +-------------------+---------------+------+-----+---------+----------------+
# | id                | int           | NO   | PRI | NULL    | auto_increment |
# | name              | varchar(32)   | NO   | UNI | NULL    |                |
# | safe_name         | varchar(32)   | NO   | UNI | NULL    |                |
# | email             | varchar(254)  | NO   | UNI | NULL    |                |
# | priv              | int           | NO   |     | 1       |                |
# | pw_bcrypt         | char(60)      | NO   |     | NULL    |                |
# | country           | char(2)       | NO   |     | xx      |                |
# | silence_end       | int           | NO   |     | 0       |                |
# | donor_end         | int           | NO   |     | 0       |                |
# | creation_time     | int           | NO   |     | 0       |                |
# | latest_activity   | int           | NO   |     | 0       |                |
# | clan_id           | int           | NO   |     | 0       |                |
# | clan_priv         | tinyint(1)    | NO   |     | 0       |                |
# | preferred_mode    | int           | NO   |     | 0       |                |
# | play_style        | int           | NO   |     | 0       |                |
# | custom_badge_name | varchar(16)   | YES  |     | NULL    |                |
# | custom_badge_icon | varchar(64)   | YES  |     | NULL    |                |
# | userpage_content  | varchar(2048) | YES  |     | NULL    |                |
# | api_key           | char(36)      | YES  | UNI | NULL    |                |
# +-------------------+---------------+------+-----+---------+----------------+

READ_PARAMS = textwrap.dedent(
    """\
        id, name, safe_name, priv, country, silence_end, donor_end, creation_time,
        latest_activity, clan_id, clan_priv, preferred_mode, play_style, custom_badge_name,
        custom_badge_icon, userpage_content
    """,
)


async def create(
    name: str,
    email: str,
    pw_bcrypt: bytes,
    country: str,
) -> dict[str, Any]:
    """Create a new player in the database."""
    query = f"""\
        INSERT INTO users (name, safe_name, email, pw_bcrypt, country, creation_time, latest_activity)
             VALUES (:name, :safe_name, :email, :pw_bcrypt, :country, UNIX_TIMESTAMP(), UNIX_TIMESTAMP())
    """
    params = {
        "name": name,
        "safe_name": make_safe_name(name),
        "email": email,
        "pw_bcrypt": pw_bcrypt,
        "country": country,
    }
    rec_id = await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM users
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
    email: Optional[str] = None,
    fetch_all_fields: bool = False,  # TODO: probably remove this if possible
) -> Optional[dict[str, Any]]:
    """Fetch a single player from the database."""
    if id is None and name is None and email is None:
        raise ValueError("Must provide at least one parameter.")

    query = f"""\
        SELECT {'*' if fetch_all_fields else READ_PARAMS}
          FROM users
         WHERE id = COALESCE(:id, id)
           AND safe_name = COALESCE(:safe_name, safe_name)
           AND email = COALESCE(:email, email)
    """
    params = {
        "id": id,
        "safe_name": make_safe_name(name) if name is not None else None,
        "email": email,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    return dict(rec) if rec is not None else None


async def fetch_count(
    priv: Optional[int] = None,
    country: Optional[str] = None,
    clan_id: Optional[int] = None,
    clan_priv: Optional[int] = None,
    preferred_mode: Optional[int] = None,
    play_style: Optional[int] = None,
) -> int:
    """Fetch the number of players in the database."""
    query = """\
        SELECT COUNT(*) AS count
          FROM users
         WHERE priv = COALESCE(:priv, priv)
           AND country = COALESCE(:country, country)
           AND clan_id = COALESCE(:clan_id, clan_id)
           AND clan_priv = COALESCE(:clan_priv, clan_priv)
           AND preferred_mode = COALESCE(:preferred_mode, preferred_mode)
           AND play_style = COALESCE(:play_style, play_style)
    """
    params = {
        "priv": priv,
        "country": country,
        "clan_id": clan_id,
        "clan_priv": clan_priv,
        "preferred_mode": preferred_mode,
        "play_style": play_style,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    assert rec is not None
    return rec["count"]


async def fetch_many(
    priv: Optional[int] = None,
    country: Optional[str] = None,
    clan_id: Optional[int] = None,
    clan_priv: Optional[int] = None,
    preferred_mode: Optional[int] = None,
    play_style: Optional[int] = None,
    page: Optional[int] = None,
    page_size: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Fetch multiple players from the database."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM users
         WHERE priv = COALESCE(:priv, priv)
           AND country = COALESCE(:country, country)
           AND clan_id = COALESCE(:clan_id, clan_id)
           AND clan_priv = COALESCE(:clan_priv, clan_priv)
           AND preferred_mode = COALESCE(:preferred_mode, preferred_mode)
           AND play_style = COALESCE(:play_style, play_style)
    """
    params = {
        "priv": priv,
        "country": country,
        "clan_id": clan_id,
        "clan_priv": clan_priv,
        "preferred_mode": preferred_mode,
        "play_style": play_style,
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
    id: int,
    name: Optional[str] = None,
    email: Optional[str] = None,
    priv: Optional[int] = None,
    country: Optional[str] = None,
    silence_end: Optional[int] = None,
    donor_end: Optional[int] = None,
    creation_time: Optional[int] = None,
    latest_activity: Optional[int] = None,
    clan_id: Optional[int] = None,
    clan_priv: Optional[int] = None,
    preferred_mode: Optional[int] = None,
    play_style: Optional[int] = None,
    custom_badge_name: Optional[str] = None,
    custom_badge_icon: Optional[str] = None,
    userpage_content: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Update a player in the database."""
    query = """\
        UPDATE users
           SET name = COALESCE(:name, name),
               safe_name = COALESCE(:safe_name, safe_name),
               email = COALESCE(:email, email),
               priv = COALESCE(:priv, priv),
               country = COALESCE(:country, country),
               silence_end = COALESCE(:silence_end, silence_end),
               donor_end = COALESCE(:donor_end, donor_end),
               creation_time = COALESCE(:creation_time, creation_time),
               latest_activity = COALESCE(:latest_activity, latest_activity),
               clan_id = COALESCE(:clan_id, clan_id),
               clan_priv = COALESCE(:clan_priv, clan_priv),
               preferred_mode = COALESCE(:preferred_mode, preferred_mode),
               play_style = COALESCE(:play_style, play_style),
               custom_badge_name = COALESCE(:custom_badge_name, custom_badge_name),
               custom_badge_icon = COALESCE(:custom_badge_icon, custom_badge_icon),
               userpage_content = COALESCE(:userpage_content, userpage_content),
               api_key = COALESCE(:api_key, api_key)
         WHERE id = :id
    """
    params = {
        "id": id,
        "name": name,
        "safe_name": make_safe_name(name) if name is not None else None,
        "email": email,
        "priv": priv,
        "country": country,
        "silence_end": silence_end,
        "donor_end": donor_end,
        "creation_time": creation_time,
        "latest_activity": latest_activity,
        "clan_id": clan_id,
        "clan_priv": clan_priv,
        "preferred_mode": preferred_mode,
        "play_style": play_style,
        "custom_badge_name": custom_badge_name,
        "custom_badge_icon": custom_badge_icon,
        "userpage_content": userpage_content,
        "api_key": api_key,
    }
    await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM users
         WHERE id = :id
    """
    params = {
        "id": id,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    return dict(rec) if rec is not None else None


# TODO: delete?
