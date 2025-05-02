from __future__ import annotations

from datetime import datetime
from typing import TypedDict
from typing import cast

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import func
from sqlalchemy import insert
from sqlalchemy import select
from sqlalchemy.dialects.mysql import VARCHAR

import app.state.services
from app.repositories import Base


class LogTable(Base):
    __tablename__ = "logs"

    id = Column("id", Integer, nullable=False, primary_key=True, autoincrement=True)
    _from = Column(
        "from",
        Integer,
        nullable=False,
        comment="both from and to are playerids",
    )
    to = Column("to", Integer, nullable=False)
    action = Column("action", String(32), nullable=False)
    msg = Column(
        "msg",
        VARCHAR(charset="utf8mb3", collation="utf8mb3_general_ci", length=2048),
        nullable=True,
    )
    time = Column("time", DateTime, nullable=False, onupdate=func.now())


READ_PARAMS = (
    LogTable.id,
    LogTable._from.label("from"),
    LogTable.to,
    LogTable.action,
    LogTable.msg,
    LogTable.time,
)


class Log(TypedDict):
    id: int
    _from: int
    to: int
    action: str
    msg: str | None
    time: datetime


async def create(
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
    rec_id = await app.state.services.database.execute(insert_stmt)

    select_stmt = select(*READ_PARAMS).where(LogTable.id == rec_id)
    log = await app.state.services.database.fetch_one(select_stmt)
    assert log is not None
    return cast(Log, log)
