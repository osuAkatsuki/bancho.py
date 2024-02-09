from __future__ import annotations

import textwrap
from typing import Any
from typing import cast
from typing import TypedDict

import app.state.services
from app._typing import _UnsetSentinel
from app._typing import UNSET
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


class Player(TypedDict):
    id: int
    name: str
    safe_name: str
    priv: int
    pw_bcrypt: str
    country: str
    silence_end: int
    donor_end: int
    creation_time: int
    latest_activity: int
    clan_id: int
    clan_priv: int
    preferred_mode: int
    play_style: int
    custom_badge_name: str | None
    custom_badge_icon: str | None
    userpage_content: str | None
    api_key: str | None


class PlayerUpdateFields(TypedDict, total=False):
    name: str
    safe_name: str
    email: str
    priv: int
    country: str
    silence_end: int
    donor_end: int
    creation_time: int
    latest_activity: int
    clan_id: int
    clan_priv: int
    preferred_mode: int
    play_style: int
    custom_badge_name: str | None
    custom_badge_icon: str | None
    userpage_content: str | None
    api_key: str | None


async def create(
    name: str,
    email: str,
    pw_bcrypt: bytes,
    country: str,
) -> Player:
    """Create a new player in the database."""
    query = f"""\
        INSERT INTO users (name, safe_name, email, pw_bcrypt, country, creation_time, latest_activity)
             VALUES (:name, :safe_name, :email, :pw_bcrypt, :country, UNIX_TIMESTAMP(), UNIX_TIMESTAMP())
    """
    params: dict[str, Any] = {
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
    player = await app.state.services.database.fetch_one(query, params)

    assert player is not None
    return cast(Player, dict(player._mapping))


async def fetch_one(
    id: int | None = None,
    name: str | None = None,
    email: str | None = None,
    fetch_all_fields: bool = False,  # TODO: probably remove this if possible
) -> Player | None:
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
    params: dict[str, Any] = {
        "id": id,
        "safe_name": make_safe_name(name) if name is not None else None,
        "email": email,
    }
    player = await app.state.services.database.fetch_one(query, params)
    return cast(Player, dict(player._mapping)) if player is not None else None


async def fetch_count(
    priv: int | None = None,
    country: str | None = None,
    clan_id: int | None = None,
    clan_priv: int | None = None,
    preferred_mode: int | None = None,
    play_style: int | None = None,
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
    params: dict[str, Any] = {
        "priv": priv,
        "country": country,
        "clan_id": clan_id,
        "clan_priv": clan_priv,
        "preferred_mode": preferred_mode,
        "play_style": play_style,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    assert rec is not None
    return cast(int, rec._mapping["count"])


async def fetch_many(
    priv: int | None = None,
    country: str | None = None,
    clan_id: int | None = None,
    clan_priv: int | None = None,
    preferred_mode: int | None = None,
    play_style: int | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[Player]:
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
    params: dict[str, Any] = {
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

    players = await app.state.services.database.fetch_all(query, params)
    return cast(list[Player], [dict(p._mapping) for p in players])


async def update(
    id: int,
    name: str | _UnsetSentinel = UNSET,
    email: str | _UnsetSentinel = UNSET,
    priv: int | _UnsetSentinel = UNSET,
    country: str | _UnsetSentinel = UNSET,
    silence_end: int | _UnsetSentinel = UNSET,
    donor_end: int | _UnsetSentinel = UNSET,
    creation_time: _UnsetSentinel | _UnsetSentinel = UNSET,
    latest_activity: int | _UnsetSentinel = UNSET,
    clan_id: int | _UnsetSentinel = UNSET,
    clan_priv: int | _UnsetSentinel = UNSET,
    preferred_mode: int | _UnsetSentinel = UNSET,
    play_style: int | _UnsetSentinel = UNSET,
    custom_badge_name: str | None | _UnsetSentinel = UNSET,
    custom_badge_icon: str | None | _UnsetSentinel = UNSET,
    userpage_content: str | None | _UnsetSentinel = UNSET,
    api_key: str | None | _UnsetSentinel = UNSET,
) -> Player | None:
    """Update a player in the database."""
    update_fields: PlayerUpdateFields = {}
    if not isinstance(name, _UnsetSentinel):
        update_fields["name"] = name
        update_fields["safe_name"] = make_safe_name(name)
    if not isinstance(email, _UnsetSentinel):
        update_fields["email"] = email
    if not isinstance(priv, _UnsetSentinel):
        update_fields["priv"] = priv
    if not isinstance(country, _UnsetSentinel):
        update_fields["country"] = country
    if not isinstance(silence_end, _UnsetSentinel):
        update_fields["silence_end"] = silence_end
    if not isinstance(donor_end, _UnsetSentinel):
        update_fields["donor_end"] = donor_end
    if not isinstance(creation_time, _UnsetSentinel):
        update_fields["creation_time"] = creation_time
    if not isinstance(latest_activity, _UnsetSentinel):
        update_fields["latest_activity"] = latest_activity
    if not isinstance(clan_id, _UnsetSentinel):
        update_fields["clan_id"] = clan_id
    if not isinstance(clan_priv, _UnsetSentinel):
        update_fields["clan_priv"] = clan_priv
    if not isinstance(preferred_mode, _UnsetSentinel):
        update_fields["preferred_mode"] = preferred_mode
    if not isinstance(play_style, _UnsetSentinel):
        update_fields["play_style"] = play_style
    if not isinstance(custom_badge_name, _UnsetSentinel):
        update_fields["custom_badge_name"] = custom_badge_name
    if not isinstance(custom_badge_icon, _UnsetSentinel):
        update_fields["custom_badge_icon"] = custom_badge_icon
    if not isinstance(userpage_content, _UnsetSentinel):
        update_fields["userpage_content"] = userpage_content
    if not isinstance(api_key, _UnsetSentinel):
        update_fields["api_key"] = api_key

    query = f"""\
        UPDATE users
           SET {",".join(f"{k} = COALESCE(:{k}, {k})" for k in update_fields)}
         WHERE id = :id
    """
    params: dict[str, Any] = {
        "id": id,
    } | update_fields
    await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM users
         WHERE id = :id
    """
    params = {
        "id": id,
    }
    player = await app.state.services.database.fetch_one(query, params)
    return cast(Player, dict(player._mapping)) if player is not None else None


# TODO: delete?
