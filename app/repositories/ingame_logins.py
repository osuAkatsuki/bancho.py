from __future__ import annotations

from datetime import date
from datetime import datetime
from typing import TypedDict
from typing import cast

from sqlalchemy import Column
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import func
from sqlalchemy import insert
from sqlalchemy import select

import app.state.services
from app.repositories import Base


class IngameLoginsTable(Base):
    __tablename__ = "ingame_logins"

    id = Column("id", Integer, nullable=False, primary_key=True, autoincrement=True)
    userid = Column("userid", Integer, nullable=False)
    ip = Column("ip", String(45), nullable=False)
    osu_ver = Column("osu_ver", Date, nullable=False)
    osu_stream = Column("osu_stream", String(11), nullable=False)
    datetime = Column("datetime", DateTime, nullable=False)


READ_PARAMS = (
    IngameLoginsTable.id,
    IngameLoginsTable.userid,
    IngameLoginsTable.ip,
    IngameLoginsTable.osu_ver,
    IngameLoginsTable.osu_stream,
    IngameLoginsTable.datetime,
)


class IngameLogin(TypedDict):
    id: int
    userid: str
    ip: str
    osu_ver: date
    osu_stream: str
    datetime: datetime


class InGameLoginUpdateFields(TypedDict, total=False):
    userid: str
    ip: str
    osu_ver: date
    osu_stream: str


async def create(
    user_id: int,
    ip: str,
    osu_ver: date,
    osu_stream: str,
) -> IngameLogin:
    """Create a new login entry in the database."""
    insert_stmt = insert(IngameLoginsTable).values(
        userid=user_id,
        ip=ip,
        osu_ver=osu_ver,
        osu_stream=osu_stream,
        datetime=func.now(),
    )
    rec_id = await app.state.services.database.execute(insert_stmt)

    select_stmt = select(*READ_PARAMS).where(IngameLoginsTable.id == rec_id)
    ingame_login = await app.state.services.database.fetch_one(select_stmt)

    assert ingame_login is not None
    return cast(IngameLogin, ingame_login)


async def fetch_one(id: int) -> IngameLogin | None:
    """Fetch a login entry from the database."""
    select_stmt = select(*READ_PARAMS).where(IngameLoginsTable.id == id)
    ingame_login = await app.state.services.database.fetch_one(select_stmt)
    return cast(IngameLogin | None, ingame_login)


async def fetch_count(
    user_id: int | None = None,
    ip: str | None = None,
) -> int:
    """Fetch the number of logins in the database."""
    select_stmt = select(func.count().label("count")).select_from(IngameLoginsTable)
    if user_id is not None:
        select_stmt = select_stmt.where(IngameLoginsTable.userid == user_id)
    if ip is not None:
        select_stmt = select_stmt.where(IngameLoginsTable.ip == ip)

    rec = await app.state.services.database.fetch_one(select_stmt)
    assert rec is not None
    return cast(int, rec["count"])


async def fetch_many(
    user_id: int | None = None,
    ip: str | None = None,
    osu_ver: date | None = None,
    osu_stream: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[IngameLogin]:
    """Fetch a list of logins from the database."""
    select_stmt = select(*READ_PARAMS)

    if user_id is not None:
        select_stmt = select_stmt.where(IngameLoginsTable.userid == user_id)
    if ip is not None:
        select_stmt = select_stmt.where(IngameLoginsTable.ip == ip)
    if osu_ver is not None:
        select_stmt = select_stmt.where(IngameLoginsTable.osu_ver == osu_ver)
    if osu_stream is not None:
        select_stmt = select_stmt.where(IngameLoginsTable.osu_stream == osu_stream)

    if page is not None and page_size is not None:
        select_stmt.limit(page_size).offset((page - 1) * page_size)

    ingame_logins = await app.state.services.database.fetch_all(select_stmt)
    return cast(list[IngameLogin], ingame_logins)
