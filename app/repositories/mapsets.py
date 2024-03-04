from __future__ import annotations

from sqlalchemy import Column
from sqlalchemy import Index
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.dialects.mysql import ENUM
from sqlalchemy.dialects.mysql import INTEGER

from app.repositories import Base


class MapsetsTable(Base):
    __tablename__ = "mapsets"

    server = Column(
        "server",
        ENUM("osu!", "private"),
        server_default="'osu!'",
        nullable=False,
        primary_key=True,
    )
    id = Column("id", INTEGER, autoincrement=False, nullable=False, primary_key=True)
    last_osuapi_check = Column(
        "last_osuapi_check",
        DATETIME,
        server_default="CURRENT_TIMESTAMP",
        nullable=False,
    )

    __table_args__ = (Index("nmapsets_id_uindex", "id", unique=True),)
