from __future__ import annotations

from typing import TypedDict
from typing import cast

from sqlalchemy import Column
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import func
from sqlalchemy import insert
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.dialects.mysql import TINYINT

import app.state.services
from app._typing import UNSET
from app._typing import _UnsetSentinel
from app.repositories import Base
from app.utils import make_safe_name


class UsersTable(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    name = Column(String(32, collation="utf8"), nullable=False)
    safe_name = Column(String(32, collation="utf8"), nullable=False)
    email = Column(String(254), nullable=False)
    priv = Column(Integer, nullable=False, server_default="1")
    pw_bcrypt = Column(String(60), nullable=False)
    country = Column(String(2), nullable=False, server_default="xx")
    silence_end = Column(Integer, nullable=False, server_default="0")
    donor_end = Column(Integer, nullable=False, server_default="0")
    creation_time = Column(Integer, nullable=False, server_default="0")
    latest_activity = Column(Integer, nullable=False, server_default="0")
    clan_id = Column(Integer, nullable=False, server_default="0")
    clan_priv = Column(TINYINT, nullable=False, server_default="0")
    preferred_mode = Column(Integer, nullable=False, server_default="0")
    play_style = Column(Integer, nullable=False, server_default="0")
    custom_badge_name = Column(String(16, collation="utf8"))
    custom_badge_icon = Column(String(64))
    userpage_content = Column(String(2048, collation="utf8"))
    api_key = Column(String(36))

    __table_args__ = (
        Index("users_priv_index", priv),
        Index("users_clan_id_index", clan_id),
        Index("users_clan_priv_index", clan_priv),
        Index("users_country_index", country),
        Index("users_api_key_uindex", api_key, unique=True),
        Index("users_email_uindex", email, unique=True),
        Index("users_name_uindex", name, unique=True),
        Index("users_safe_name_uindex", safe_name, unique=True),
    )


READ_PARAMS = (
    UsersTable.id,
    UsersTable.name,
    UsersTable.safe_name,
    UsersTable.priv,
    UsersTable.country,
    UsersTable.silence_end,
    UsersTable.donor_end,
    UsersTable.creation_time,
    UsersTable.latest_activity,
    UsersTable.clan_id,
    UsersTable.clan_priv,
    UsersTable.preferred_mode,
    UsersTable.play_style,
    UsersTable.custom_badge_name,
    UsersTable.custom_badge_icon,
    UsersTable.userpage_content,
)


class User(TypedDict):
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


async def create(
    name: str,
    email: str,
    pw_bcrypt: bytes,
    country: str,
) -> User:
    """Create a new user in the database."""
    insert_stmt = insert(UsersTable).values(
        name=name,
        safe_name=make_safe_name(name),
        email=email,
        pw_bcrypt=pw_bcrypt,
        country=country,
        creation_time=func.unix_timestamp(),
        latest_activity=func.unix_timestamp(),
    )
    rec_id = await app.state.services.database.execute(insert_stmt)

    select_stmt = select(*READ_PARAMS).where(UsersTable.id == rec_id)
    user = await app.state.services.database.fetch_one(select_stmt)
    assert user is not None
    return cast(User, user)


async def fetch_one(
    id: int | None = None,
    name: str | None = None,
    email: str | None = None,
    fetch_all_fields: bool = False,  # TODO: probably remove this if possible
) -> User | None:
    """Fetch a single user from the database."""
    if id is None and name is None and email is None:
        raise ValueError("Must provide at least one parameter.")

    if fetch_all_fields:
        select_stmt = select(UsersTable)
    else:
        select_stmt = select(*READ_PARAMS)

    if id is not None:
        select_stmt = select_stmt.where(UsersTable.id == id)
    if name is not None:
        select_stmt = select_stmt.where(UsersTable.safe_name == make_safe_name(name))
    if email is not None:
        select_stmt = select_stmt.where(UsersTable.email == email)

    user = await app.state.services.database.fetch_one(select_stmt)
    return cast(User | None, user)


async def fetch_count(
    priv: int | None = None,
    country: str | None = None,
    clan_id: int | None = None,
    clan_priv: int | None = None,
    preferred_mode: int | None = None,
    play_style: int | None = None,
) -> int:
    """Fetch the number of users in the database."""
    select_stmt = select(func.count().label("count")).select_from(UsersTable)
    if priv is not None:
        select_stmt = select_stmt.where(UsersTable.priv == priv)
    if country is not None:
        select_stmt = select_stmt.where(UsersTable.country == country)
    if clan_id is not None:
        select_stmt = select_stmt.where(UsersTable.clan_id == clan_id)
    if clan_priv is not None:
        select_stmt = select_stmt.where(UsersTable.clan_priv == clan_priv)
    if preferred_mode is not None:
        select_stmt = select_stmt.where(UsersTable.preferred_mode == preferred_mode)
    if play_style is not None:
        select_stmt = select_stmt.where(UsersTable.play_style == play_style)

    rec = await app.state.services.database.fetch_one(select_stmt)
    assert rec is not None
    return cast(int, rec["count"])


async def fetch_many(
    priv: int | None = None,
    country: str | None = None,
    clan_id: int | None = None,
    clan_priv: int | None = None,
    preferred_mode: int | None = None,
    play_style: int | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[User]:
    """Fetch multiple users from the database."""
    select_stmt = select(*READ_PARAMS)
    if priv is not None:
        select_stmt = select_stmt.where(UsersTable.priv == priv)
    if country is not None:
        select_stmt = select_stmt.where(UsersTable.country == country)
    if clan_id is not None:
        select_stmt = select_stmt.where(UsersTable.clan_id == clan_id)
    if clan_priv is not None:
        select_stmt = select_stmt.where(UsersTable.clan_priv == clan_priv)
    if preferred_mode is not None:
        select_stmt = select_stmt.where(UsersTable.preferred_mode == preferred_mode)
    if play_style is not None:
        select_stmt = select_stmt.where(UsersTable.play_style == play_style)

    if page is not None and page_size is not None:
        select_stmt = select_stmt.limit(page_size).offset((page - 1) * page_size)

    users = await app.state.services.database.fetch_all(select_stmt)
    return cast(list[User], users)


async def partial_update(
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
) -> User | None:
    """Update a user in the database."""
    update_stmt = update(UsersTable).where(UsersTable.id == id)
    if not isinstance(name, _UnsetSentinel):
        update_stmt = update_stmt.values(name=name, safe_name=make_safe_name(name))
    if not isinstance(email, _UnsetSentinel):
        update_stmt = update_stmt.values(email=email)
    if not isinstance(priv, _UnsetSentinel):
        update_stmt = update_stmt.values(priv=priv)
    if not isinstance(country, _UnsetSentinel):
        update_stmt = update_stmt.values(country=country)
    if not isinstance(silence_end, _UnsetSentinel):
        update_stmt = update_stmt.values(silence_end=silence_end)
    if not isinstance(donor_end, _UnsetSentinel):
        update_stmt = update_stmt.values(donor_end=donor_end)
    if not isinstance(creation_time, _UnsetSentinel):
        update_stmt = update_stmt.values(creation_time=creation_time)
    if not isinstance(latest_activity, _UnsetSentinel):
        update_stmt = update_stmt.values(latest_activity=latest_activity)
    if not isinstance(clan_id, _UnsetSentinel):
        update_stmt = update_stmt.values(clan_id=clan_id)
    if not isinstance(clan_priv, _UnsetSentinel):
        update_stmt = update_stmt.values(clan_priv=clan_priv)
    if not isinstance(preferred_mode, _UnsetSentinel):
        update_stmt = update_stmt.values(preferred_mode=preferred_mode)
    if not isinstance(play_style, _UnsetSentinel):
        update_stmt = update_stmt.values(play_style=play_style)
    if not isinstance(custom_badge_name, _UnsetSentinel):
        update_stmt = update_stmt.values(custom_badge_name=custom_badge_name)
    if not isinstance(custom_badge_icon, _UnsetSentinel):
        update_stmt = update_stmt.values(custom_badge_icon=custom_badge_icon)
    if not isinstance(userpage_content, _UnsetSentinel):
        update_stmt = update_stmt.values(userpage_content=userpage_content)
    if not isinstance(api_key, _UnsetSentinel):
        update_stmt = update_stmt.values(api_key=api_key)

    await app.state.services.database.execute(update_stmt)

    select_stmt = select(*READ_PARAMS).where(UsersTable.id == id)
    user = await app.state.services.database.fetch_one(select_stmt)
    return cast(User | None, user)


# TODO: delete?
