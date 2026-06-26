from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import func
from sqlalchemy import insert
from sqlalchemy import select

from app.adapters.database import Database
from app.adapters.database import MySQLRow
from app.repositories import Base


class LogTable(Base):
    __tablename__ = "logs"

    id = Column("id", Integer, nullable=False, primary_key=True, autoincrement=True)
    _from = Column("from", Integer, nullable=False)
    to = Column("to", Integer, nullable=False)
    action = Column("action", String(32), nullable=False)
    msg = Column("msg", String(2048, collation="utf8"), nullable=True)
    time = Column("time", DateTime, nullable=False, onupdate=func.now())


READ_PARAMS = (
    LogTable.id,
    LogTable._from.label("from"),
    LogTable.to,
    LogTable.action,
    LogTable.msg,
    LogTable.time,
)


@dataclass(frozen=True, slots=True)
class Log:
    id: int
    _from: int
    to: int
    action: str
    msg: str | None
    time: datetime


class LogsRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def _deserialize_log(self, row: MySQLRow) -> Log:
        return Log(
            id=row["id"],
            _from=row["from"],
            to=row["to"],
            action=row["action"],
            msg=row["msg"],
            time=row["time"],
        )

    async def create(
        self,
        _from: int,
        to: int,
        action: str,
        msg: str,
    ) -> Log:
        """Create a new log entry in the database."""
        insert_stmt = insert(LogTable).values(
            {
                "from": _from,
                "to": to,
                "action": action,
                "msg": msg,
                "time": func.now(),
            },
        )
        rec_id = await self._database.execute(insert_stmt)

        select_stmt = select(*READ_PARAMS).where(LogTable.id == rec_id)
        log = await self._database.fetch_one(select_stmt)
        assert log is not None
        return self._deserialize_log(log)
