from __future__ import annotations

from typing import TypedDict
from typing import cast

from sqlalchemy import Column
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import delete
from sqlalchemy import func
from sqlalchemy import insert
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.dialects.mysql import TINYINT

import app.state.services
from app._typing import UNSET
from app._typing import _UnsetSentinel
from app.repositories import Base


class ChannelsTable(Base):
    __tablename__ = "channels"

    id = Column("id", Integer, primary_key=True, nullable=False, autoincrement=True)
    name = Column("name", String(32), nullable=False)
    topic = Column("topic", String(256), nullable=False)
    read_priv = Column("read_priv", Integer, nullable=False, server_default="1")
    write_priv = Column("write_priv", Integer, nullable=False, server_default="2")
    auto_join = Column("auto_join", TINYINT(1), nullable=False, server_default="0")

    __table_args__ = (
        Index("channels_name_uindex", name, unique=True),
        Index("channels_auto_join_index", auto_join),
    )


READ_PARAMS = (
    ChannelsTable.id,
    ChannelsTable.name,
    ChannelsTable.topic,
    ChannelsTable.read_priv,
    ChannelsTable.write_priv,
    ChannelsTable.auto_join,
)


class Channel(TypedDict):
    id: int
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
    insert_stmt = insert(ChannelsTable).values(
        name=name,
        topic=topic,
        read_priv=read_priv,
        write_priv=write_priv,
        auto_join=auto_join,
    )
    rec_id = await app.state.services.database.execute(insert_stmt)

    select_stmt = select(*READ_PARAMS).where(ChannelsTable.id == rec_id)
    channel = await app.state.services.database.fetch_one(select_stmt)

    assert channel is not None
    return cast(Channel, channel)


async def fetch_one(
    id: int | None = None,
    name: str | None = None,
) -> Channel | None:
    """Fetch a single channel."""
    if id is None and name is None:
        raise ValueError("Must provide at least one parameter.")

    select_stmt = select(*READ_PARAMS)

    if id is not None:
        select_stmt = select_stmt.where(ChannelsTable.id == id)
    if name is not None:
        select_stmt = select_stmt.where(ChannelsTable.name == name)

    channel = await app.state.services.database.fetch_one(select_stmt)
    return cast(Channel | None, channel)


async def fetch_count(
    read_priv: int | None = None,
    write_priv: int | None = None,
    auto_join: bool | None = None,
) -> int:
    if read_priv is None and write_priv is None and auto_join is None:
        raise ValueError("Must provide at least one parameter.")

    select_stmt = select(func.count().label("count")).select_from(ChannelsTable)

    if read_priv is not None:
        select_stmt = select_stmt.where(ChannelsTable.read_priv == read_priv)
    if write_priv is not None:
        select_stmt = select_stmt.where(ChannelsTable.write_priv == write_priv)
    if auto_join is not None:
        select_stmt = select_stmt.where(ChannelsTable.auto_join == auto_join)

    rec = await app.state.services.database.fetch_one(select_stmt)
    assert rec is not None
    return cast(int, rec["count"])


async def fetch_many(
    read_priv: int | None = None,
    write_priv: int | None = None,
    auto_join: bool | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[Channel]:
    """Fetch multiple channels from the database."""
    select_stmt = select(*READ_PARAMS)

    if read_priv is not None:
        select_stmt = select_stmt.where(ChannelsTable.read_priv == read_priv)
    if write_priv is not None:
        select_stmt = select_stmt.where(ChannelsTable.write_priv == write_priv)
    if auto_join is not None:
        select_stmt = select_stmt.where(ChannelsTable.auto_join == auto_join)

    if page is not None and page_size is not None:
        select_stmt = select_stmt.limit(page_size).offset((page - 1) * page_size)

    channels = await app.state.services.database.fetch_all(select_stmt)
    return cast(list[Channel], channels)


async def partial_update(
    name: str,
    topic: str | _UnsetSentinel = UNSET,
    read_priv: int | _UnsetSentinel = UNSET,
    write_priv: int | _UnsetSentinel = UNSET,
    auto_join: bool | _UnsetSentinel = UNSET,
) -> Channel | None:
    """Update a channel in the database."""
    update_stmt = update(ChannelsTable).where(ChannelsTable.name == name)

    if not isinstance(topic, _UnsetSentinel):
        update_stmt = update_stmt.values(topic=topic)
    if not isinstance(read_priv, _UnsetSentinel):
        update_stmt = update_stmt.values(read_priv=read_priv)
    if not isinstance(write_priv, _UnsetSentinel):
        update_stmt = update_stmt.values(write_priv=write_priv)
    if not isinstance(auto_join, _UnsetSentinel):
        update_stmt = update_stmt.values(auto_join=auto_join)

    await app.state.services.database.execute(update_stmt)

    select_stmt = select(*READ_PARAMS).where(ChannelsTable.name == name)
    channel = await app.state.services.database.fetch_one(select_stmt)
    return cast(Channel | None, channel)


async def delete_one(
    name: str,
) -> Channel | None:
    """Delete a channel from the database."""
    select_stmt = select(*READ_PARAMS).where(ChannelsTable.name == name)
    channel = await app.state.services.database.fetch_one(select_stmt)
    if channel is None:
        return None

    delete_stmt = delete(ChannelsTable).where(ChannelsTable.name == name)
    await app.state.services.database.execute(delete_stmt)
    return cast(Channel | None, channel)
