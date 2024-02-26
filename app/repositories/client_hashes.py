from __future__ import annotations

from datetime import datetime
from typing import TypedDict
from typing import cast

from sqlalchemy import CHAR
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.dialects.mysql import Insert as MysqlInsert
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.sql import ColumnElement
from sqlalchemy.types import Boolean

import app.state.services
from app.repositories import Base
from app.repositories.users import UsersTable


class ClientHashesTable(Base):
    __tablename__ = "client_hashes"

    userid = Column("userid", Integer, nullable=False, primary_key=True)
    osupath = Column("osupath", CHAR(32), nullable=False, primary_key=True)
    adapters = Column("adapters", CHAR(32), nullable=False, primary_key=True)
    uninstall_id = Column("uninstall_id", CHAR(32), nullable=False, primary_key=True)
    disk_serial = Column("disk_serial", CHAR(32), nullable=False, primary_key=True)
    latest_time = Column("latest_time", DateTime, nullable=False)
    occurrences = Column("occurrences", Integer, nullable=False, server_default="0")


READ_PARAMS = (
    ClientHashesTable.userid,
    ClientHashesTable.osupath,
    ClientHashesTable.adapters,
    ClientHashesTable.uninstall_id,
    ClientHashesTable.disk_serial,
    ClientHashesTable.latest_time,
    ClientHashesTable.occurrences,
)


class ClientHash(TypedDict):
    userid: int
    osupath: str
    adapters: str
    uninstall_id: str
    disk_serial: str
    latest_time: datetime
    occurrences: int


class ClientHashWithPlayer(ClientHash):
    name: str
    priv: int


async def create(
    userid: int,
    osupath: str,
    adapters: str,
    uninstall_id: str,
    disk_serial: str,
) -> ClientHash:
    """Create a new client hash entry in the database."""
    insert_stmt: MysqlInsert = (
        mysql_insert(ClientHashesTable)
        .values(
            userid=userid,
            osupath=osupath,
            adapters=adapters,
            uninstall_id=uninstall_id,
            disk_serial=disk_serial,
            latest_time=func.now(),
            occurrences=1,
        )
        .on_duplicate_key_update(
            latest_time=func.now(),
            occurrences=ClientHashesTable.occurrences + 1,
        )
    )

    await app.state.services.database.execute(insert_stmt)

    select_stmt = (
        select(*READ_PARAMS)
        .where(ClientHashesTable.userid == userid)
        .where(ClientHashesTable.osupath == osupath)
        .where(ClientHashesTable.adapters == adapters)
        .where(ClientHashesTable.uninstall_id == uninstall_id)
        .where(ClientHashesTable.disk_serial == disk_serial)
    )
    client_hash = await app.state.services.database.fetch_one(select_stmt)

    assert client_hash is not None
    return cast(ClientHash, client_hash)


async def fetch_any_hardware_matches_for_user(
    userid: int,
    running_under_wine: bool,
    adapters: str,
    uninstall_id: str,
    disk_serial: str | None = None,
) -> list[ClientHashWithPlayer]:
    """\
    Fetch a list of matching hardware addresses where any of
    `adapters`, `uninstall_id` or `disk_serial` match other users
    from the database.
    """
    select_stmt = (
        select(*READ_PARAMS, UsersTable.name, UsersTable.priv)
        .join(UsersTable, ClientHashesTable.userid == UsersTable.id)
        .where(ClientHashesTable.userid != userid)
    )

    if running_under_wine:
        select_stmt = select_stmt.where(ClientHashesTable.uninstall_id == uninstall_id)
    else:
        # make disk serial optional in the OR
        oneof_filters: list[ColumnElement[Boolean]] = []
        oneof_filters.append(ClientHashesTable.adapters == adapters)
        oneof_filters.append(ClientHashesTable.uninstall_id == uninstall_id)
        if disk_serial is not None:
            oneof_filters.append(ClientHashesTable.disk_serial == disk_serial)
        select_stmt = select_stmt.where(or_(*oneof_filters))

    client_hashes = await app.state.services.database.fetch_all(select_stmt)
    return cast(list[ClientHashWithPlayer], client_hashes)
