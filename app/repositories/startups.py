from __future__ import annotations

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.dialects.mysql import INTEGER

from app.repositories import Base


class StartupsTable(Base):
    __tablename__ = "startups"

    id = Column(INTEGER, autoincrement=True, nullable=False, primary_key=True)
    ver_major = Column(TINYINT, nullable=False)
    ver_minor = Column(TINYINT, nullable=False)
    ver_micro = Column(TINYINT, nullable=False)
    datetime = Column(DateTime, nullable=False)