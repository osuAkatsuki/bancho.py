from __future__ import annotations

import textwrap
from typing import Any
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
from app.repositories import DIALECT
from app.repositories import Base

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


class ChannelsTable(Base):
    __tablename__ = "channels"

    id = Column("id", Integer, primary_key=True)
    name = Column("name", String(32), nullable=False)
    topic = Column("topic", String(256), nullable=False)
    read_priv = Column("read_priv", Integer, nullable=False, default=1)
    write_priv = Column("write_priv", Integer, nullable=False, default=2)
    auto_join = Column("auto_join", TINYINT(1), nullable=False, default=0)

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
    compiled = insert_stmt.compile(dialect=DIALECT)
    rec_id = await app.state.services.database.execute(str(compiled), compiled.params)

    select_stmt = select(READ_PARAMS).where(ChannelsTable.id == rec_id)
    compiled = select_stmt.compile(dialect=DIALECT)
    channel = await app.state.services.database.fetch_one(
        str(compiled),
        compiled.params,
    )

    assert channel is not None
    return cast(Channel, dict(channel._mapping))


async def fetch_one(
    id: int | None = None,
    name: str | None = None,
) -> Channel | None:
    """Fetch a single channel."""
    if id is None and name is None:
        raise ValueError("Must provide at least one parameter.")

    select_stmt = select(READ_PARAMS)

    if id is not None:
        select_stmt = select_stmt.where(ChannelsTable.id == id)
    if name is not None:
        select_stmt = select_stmt.where(ChannelsTable.name == name)

    compiled = select_stmt.compile(dialect=DIALECT)
    channel = await app.state.services.database.fetch_one(
        str(compiled),
        compiled.params,
    )

    return cast(Channel, dict(channel._mapping)) if channel is not None else None


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

    compiled = select_stmt.compile(dialect=DIALECT)
    rec = await app.state.services.database.fetch_one(str(compiled), compiled.params)
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
    select_stmt = select(READ_PARAMS)

    if read_priv is not None:
        select_stmt = select_stmt.where(ChannelsTable.read_priv == read_priv)
    if write_priv is not None:
        select_stmt = select_stmt.where(ChannelsTable.write_priv == write_priv)
    if auto_join is not None:
        select_stmt = select_stmt.where(ChannelsTable.auto_join == auto_join)

    if page is not None and page_size is not None:
        select_stmt = select_stmt.limit(page_size).offset((page - 1) * page_size)

    compiled = select_stmt.compile(dialect=DIALECT)
    channels = await app.state.services.database.fetch_all(
        str(compiled),
        compiled.params,
    )
    return cast(list[Channel], [dict(c._mapping) for c in channels])


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

    compiled = update_stmt.compile(dialect=DIALECT)
    await app.state.services.database.execute(str(compiled), compiled.params)

    select_stmt = select(READ_PARAMS).where(ChannelsTable.name == name)
    compiled = select_stmt.compile(dialect=DIALECT)
    channel = await app.state.services.database.fetch_one(
        str(compiled),
        compiled.params,
    )
    return cast(Channel, dict(channel._mapping)) if channel is not None else None


async def delete_one(
    name: str,
) -> Channel | None:
    """Delete a channel from the database."""
    select_stmt = select(READ_PARAMS).where(ChannelsTable.name == name)
    compiled = select_stmt.compile(dialect=DIALECT)
    rec = await app.state.services.database.fetch_one(str(compiled), compiled.params)
    if rec is None:
        return None

    delete_stmt = delete(ChannelsTable).where(ChannelsTable.name == name)
    compiled = delete_stmt.compile(dialect=DIALECT)
    await app.state.services.database.execute(str(compiled), compiled.params)
    return cast(Channel, dict(rec._mapping)) if rec is not None else None
