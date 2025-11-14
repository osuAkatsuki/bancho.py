from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TypedDict
from typing import cast

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Enum
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import delete
from sqlalchemy import func
from sqlalchemy import insert
from sqlalchemy import select
from sqlalchemy import update

import app.state.services
from app._typing import UNSET
from app._typing import _UnsetSentinel
from app.repositories import Base


class MapsetServer(StrEnum):
    OSU = "osu!"
    PRIVATE = "private"


class MapsetTable(Base):
    __tablename__ = "mapsets"

    server = Column(
        Enum(MapsetServer, name="server"),
        nullable=False,
        server_default="osu!",
        primary_key=True,
    )
    id = Column(Integer, nullable=False, primary_key=True)
    last_osuapi_check = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (Index("nmapsets_id_uindex", "id", unique=True),)


READ_PARAMS = (
    MapsetTable.id,
    MapsetTable.server,
    MapsetTable.last_osuapi_check,
)


class Mapset(TypedDict):
    id: int
    server: str
    last_osuapi_check: datetime


async def create(
    id: int,
    server: str,
    last_osuapi_check: datetime,
) -> Mapset:
    """Create a new beatmapset entry in the database."""
    insert_stmt = insert(MapsetTable).values(
        id=id,
        server=server,
        last_osuapi_check=last_osuapi_check,
    )
    await app.state.services.database.execute(insert_stmt)

    select_stmt = select(*READ_PARAMS).where(MapsetTable.id == id)
    mapset = await app.state.services.database.fetch_one(select_stmt)
    assert mapset is not None
    return cast(Mapset, mapset)


async def partial_update(
    id: int,
    server: str | _UnsetSentinel = UNSET,
    last_osuapi_check: datetime | _UnsetSentinel = UNSET,
) -> Mapset | None:
    """Update a beatmapset entry in the database."""
    update_stmt = update(MapsetTable).where(MapsetTable.id == id)
    if not isinstance(server, _UnsetSentinel):
        update_stmt = update_stmt.values(server=server)
    if not isinstance(last_osuapi_check, _UnsetSentinel):
        update_stmt = update_stmt.values(last_osuapi_check=last_osuapi_check)

    await app.state.services.database.execute(update_stmt)

    select_stmt = select(*READ_PARAMS).where(MapsetTable.id == id)
    mapset = await app.state.services.database.fetch_one(select_stmt)
    return cast(Mapset | None, mapset)


async def delete_one(id: int) -> Mapset | None:
    """Delete a beatmapset entry in the database."""
    select_stmt = select(*READ_PARAMS).where(MapsetTable.id == id)
    mapset = await app.state.services.database.fetch_one(select_stmt)
    if mapset is None:
        return None

    delete_stmt = delete(MapsetTable).where(MapsetTable.id == id)
    await app.state.services.database.execute(delete_stmt)
    return cast(Mapset, mapset)
