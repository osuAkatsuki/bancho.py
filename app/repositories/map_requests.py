from __future__ import annotations

from datetime import datetime
from typing import Any
from typing import TypedDict
from typing import cast

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import func
from sqlalchemy import insert
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.dialects.mysql import TINYINT

import app.state.services
from app.repositories import Base


class MapRequestsTable(Base):
    __tablename__ = "map_requests"

    id = Column("id", Integer, nullable=False, primary_key=True, autoincrement=True)
    map_id = Column("map_id", Integer, nullable=False)
    player_id = Column("player_id", Integer, nullable=False)
    datetime = Column("datetime", DateTime, nullable=False)
    active = Column("active", TINYINT(1), nullable=False)


READ_PARAMS = (
    MapRequestsTable.id,
    MapRequestsTable.map_id,
    MapRequestsTable.player_id,
    MapRequestsTable.datetime,
)


class MapRequest(TypedDict):
    id: int
    map_id: int
    player_id: int
    datetime: datetime
    active: bool


async def create(
    map_id: int,
    player_id: int,
    active: bool,
) -> MapRequest:
    """Create a new map request entry in the database."""
    insert_stmt = insert(MapRequestsTable).values(
        map_id=map_id,
        player_id=player_id,
        datetime=func.now(),
        active=active,
    )
    rec_id = await app.state.services.database.execute(insert_stmt)

    select_stmt = select(*READ_PARAMS).where(MapRequestsTable.id == rec_id)
    map_request = await app.state.services.database.fetch_one(select_stmt)
    assert map_request is not None

    return cast(MapRequest, map_request)


async def fetch_all(
    map_id: int | None = None,
    player_id: int | None = None,
    active: bool | None = None,
) -> list[MapRequest]:
    """Fetch a list of map requests from the database."""
    select_stmt = select(*READ_PARAMS)
    if map_id is not None:
        select_stmt = select_stmt.where(MapRequestsTable.map_id == map_id)
    if player_id is not None:
        select_stmt = select_stmt.where(MapRequestsTable.player_id == player_id)
    if active is not None:
        select_stmt = select_stmt.where(MapRequestsTable.active == active)

    map_requests = await app.state.services.database.fetch_all(select_stmt)
    return cast(list[MapRequest], map_requests)


async def mark_batch_as_inactive(map_ids: list[Any]) -> list[MapRequest]:
    """Mark a map request as inactive."""
    update_stmt = (
        update(MapRequestsTable)
        .where(MapRequestsTable.map_id.in_(map_ids))
        .values(active=False)
    )
    await app.state.services.database.execute(update_stmt)

    select_stmt = select(*READ_PARAMS).where(MapRequestsTable.map_id.in_(map_ids))
    map_requests = await app.state.services.database.fetch_all(select_stmt)
    return cast(list[MapRequest], map_requests)
