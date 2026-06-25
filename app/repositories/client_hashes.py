from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

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

from app.adapters.database import Database
from app.adapters.database import MySQLRow
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


@dataclass(frozen=True, slots=True)
class ClientHash:
    userid: int
    osupath: str
    adapters: str
    uninstall_id: str
    disk_serial: str
    latest_time: datetime
    occurrences: int


@dataclass(frozen=True, slots=True)
class ClientHashWithPlayer:
    userid: int
    osupath: str
    adapters: str
    uninstall_id: str
    disk_serial: str
    latest_time: datetime
    occurrences: int
    name: str
    priv: int


class ClientHashesRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def _serialize_client_hash(self, client_hash: ClientHash) -> MySQLRow:
        return {
            "userid": client_hash.userid,
            "osupath": client_hash.osupath,
            "adapters": client_hash.adapters,
            "uninstall_id": client_hash.uninstall_id,
            "disk_serial": client_hash.disk_serial,
            "latest_time": client_hash.latest_time,
            "occurrences": client_hash.occurrences,
        }

    def _deserialize_client_hash(self, row: MySQLRow) -> ClientHash:
        return ClientHash(
            userid=row["userid"],
            osupath=row["osupath"],
            adapters=row["adapters"],
            uninstall_id=row["uninstall_id"],
            disk_serial=row["disk_serial"],
            latest_time=row["latest_time"],
            occurrences=row["occurrences"],
        )

    def _serialize_client_hash_with_player(
        self,
        client_hash: ClientHashWithPlayer,
    ) -> MySQLRow:
        return {
            "userid": client_hash.userid,
            "osupath": client_hash.osupath,
            "adapters": client_hash.adapters,
            "uninstall_id": client_hash.uninstall_id,
            "disk_serial": client_hash.disk_serial,
            "latest_time": client_hash.latest_time,
            "occurrences": client_hash.occurrences,
            "name": client_hash.name,
            "priv": client_hash.priv,
        }

    def _deserialize_client_hash_with_player(
        self,
        row: MySQLRow,
    ) -> ClientHashWithPlayer:
        return ClientHashWithPlayer(
            userid=row["userid"],
            osupath=row["osupath"],
            adapters=row["adapters"],
            uninstall_id=row["uninstall_id"],
            disk_serial=row["disk_serial"],
            latest_time=row["latest_time"],
            occurrences=row["occurrences"],
            name=row["name"],
            priv=row["priv"],
        )

    async def create(
        self,
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

        await self._database.execute(insert_stmt)

        select_stmt = (
            select(*READ_PARAMS)
            .where(ClientHashesTable.userid == userid)
            .where(ClientHashesTable.osupath == osupath)
            .where(ClientHashesTable.adapters == adapters)
            .where(ClientHashesTable.uninstall_id == uninstall_id)
            .where(ClientHashesTable.disk_serial == disk_serial)
        )
        client_hash = await self._database.fetch_one(select_stmt)

        assert client_hash is not None
        return self._deserialize_client_hash(client_hash)

    async def fetch_any_hardware_matches_for_user(
        self,
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
            select_stmt = select_stmt.where(
                ClientHashesTable.uninstall_id == uninstall_id,
            )
        else:
            # make disk serial optional in the OR
            oneof_filters: list[ColumnElement[Boolean]] = []
            oneof_filters.append(ClientHashesTable.adapters == adapters)
            oneof_filters.append(ClientHashesTable.uninstall_id == uninstall_id)
            if disk_serial is not None:
                oneof_filters.append(ClientHashesTable.disk_serial == disk_serial)
            select_stmt = select_stmt.where(or_(*oneof_filters))

        client_hashes = await self._database.fetch_all(select_stmt)
        return [
            self._deserialize_client_hash_with_player(client_hash)
            for client_hash in client_hashes
        ]
