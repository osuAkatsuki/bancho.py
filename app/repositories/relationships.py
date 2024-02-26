from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Column
from sqlalchemy.dialects.mysql import ENUM
from sqlalchemy.dialects.mysql import INTEGER

from app.repositories import Base


class RelationshipType(StrEnum):
    friend = "friend"
    block = "block"


class RelationshipsTable(Base):
    __tablename__ = "relationships"

    user1 = Column(
        "user1",
        INTEGER,
        autoincrement=False,
        nullable=False,
        primary_key=True,
    )
    user2 = Column(
        "user2",
        INTEGER,
        autoincrement=False,
        nullable=False,
        primary_key=True,
    )
    type = Column("type", ENUM(RelationshipType), nullable=False)
