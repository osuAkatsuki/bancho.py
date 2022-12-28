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
        id, name, safe_name, email, priv, country, silence_end, donor_end, creation_time,
        last_activity, clan_id, clan_priv, preferred_mode, play_style, custom_badge_name,
        custom_badge_icon, userpage_content
    """,
)


async def create(
    name: str,
    email: str,
    pw_bcrypt: str,
    country: str,
) -> dict[str, Any]:
    """Create a new player in the database."""
    query = f"""\
        INSERT INTO users (name, safe_name, email, pw_bcrypt, country)
             VALUES (:name, :safe_name, :email, :pw_bcrypt, :country)
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
    return rec


async def fetch_one(
    id: Optional[int] = None,
    safe_name: Optional[str] = None,
    email: Optional[str] = None,
) -> dict[str, Any]:
    """Fetch a single player from the database."""
    if not (id or safe_name or email):
        raise ValueError("Must provide at least one parameter.")

    query = f"""\
        SELECT {READ_PARAMS}
          FROM users
         WHERE id = COALESCE(:id, id)
           AND safe_name = COALESCE(:safe_name, safe_name)
           AND email = COALESCE(:email, email)
    """
    params = {
        "id": id,
        "safe_name": safe_name,
        "email": email,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    return rec


async def fetch_many(
    priv: Optional[int] = None,
    country: Optional[str] = None,
    clan_id: Optional[int] = None,
    clan_priv: Optional[int] = None,
    preferred_mode: Optional[int] = None,
    play_style: Optional[int] = None,
    page: int = 1,
    page_size: int = 100,
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
         LIMIT :limit
        OFFSET :offset
    """
    params = {
        "priv": priv,
        "country": country,
        "clan_id": clan_id,
        "clan_priv": clan_priv,
        "preferred_mode": preferred_mode,
        "play_style": play_style,
        "limit": page_size,
        "offset": (page - 1) * page_size,
    }
    recs = await app.state.services.database.fetch_all(query, params)
    return recs


async def update(
    id: int,
    name: Optional[str] = None,
    email: Optional[str] = None,
    priv: Optional[int] = None,
    country: Optional[str] = None,
    silence_end: Optional[int] = None,
    donor_end: Optional[int] = None,
    creation_time: Optional[int] = None,
    last_activity: Optional[int] = None,
    clan_id: Optional[int] = None,
    clan_priv: Optional[int] = None,
    preferred_mode: Optional[int] = None,
    play_style: Optional[int] = None,
    custom_badge_name: Optional[str] = None,
    custom_badge_icon: Optional[str] = None,
    userpage_content: Optional[str] = None,
) -> None:
    """Update a player in the database."""
    query = f"""\
        UPDATE users
           SET name = COALESCE(:name, name),
               safe_name = COALESCE(:safe_name, safe_name),
               email = COALESCE(:email, email),
               priv = COALESCE(:priv, priv),
               country = COALESCE(:country, country),
               silence_end = COALESCE(:silence_end, silence_end),
               donor_end = COALESCE(:donor_end, donor_end),
               creation_time = COALESCE(:creation_time, creation_time),
               last_activity = COALESCE(:last_activity, last_activity),
               clan_id = COALESCE(:clan_id, clan_id),
               clan_priv = COALESCE(:clan_priv, clan_priv),
               preferred_mode = COALESCE(:preferred_mode, preferred_mode),
               play_style = COALESCE(:play_style, play_style),
               custom_badge_name = COALESCE(:custom_badge_name, custom_badge_name),
               custom_badge_icon = COALESCE(:custom_badge_icon, custom_badge_icon),
               userpage_content = COALESCE(:userpage_content, userpage_content)
         WHERE id = :id
    """
    params = {
        "id": id,
        "name": name,
        "safe_name": make_safe_name(name),
        "email": email,
        "priv": priv,
        "country": country,
        "silence_end": silence_end,
        "donor_end": donor_end,
        "creation_time": creation_time,
        "last_activity": last_activity,
        "clan_id": clan_id,
        "clan_priv": clan_priv,
        "preferred_mode": preferred_mode,
        "play_style": play_style,
        "custom_badge_name": custom_badge_name,
        "custom_badge_icon": custom_badge_icon,
        "userpage_content": userpage_content,
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
    return rec


# TODO: delete?
