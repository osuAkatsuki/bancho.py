from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import Column
from sqlalchemy import Enum
from sqlalchemy import Integer
from sqlalchemy import delete
from sqlalchemy import insert
from sqlalchemy import select

from app.adapters.database import Database
from app.adapters.database import MySQLRow
from app.repositories import Base


class RelationshipType(StrEnum):
    FRIEND = "friend"
    BLOCK = "block"


class RelationshipsTable(Base):
    __tablename__ = "relationships"

    user1 = Column("user1", Integer, nullable=False, primary_key=True)
    user2 = Column("user2", Integer, nullable=False, primary_key=True)
    type = Column("type", Enum(RelationshipType, name="type"), nullable=False)


READ_PARAMS = (
    RelationshipsTable.user1,
    RelationshipsTable.user2,
    RelationshipsTable.type,
)


@dataclass(frozen=True, slots=True)
class Relationship:
    user1: int
    user2: int
    type: RelationshipType


class RelationshipsRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def _deserialize_relationship(self, row: MySQLRow) -> Relationship:
        return Relationship(
            user1=row["user1"],
            user2=row["user2"],
            type=RelationshipType(row["type"]),
        )

    async def create(
        self,
        user1: int,
        user2: int,
        type: RelationshipType,
    ) -> Relationship:
        """Create a new relationship between two users."""
        insert_stmt = insert(RelationshipsTable).values(
            user1=user1,
            user2=user2,
            type=type,
        )
        await self._database.execute(insert_stmt)

        select_stmt = (
            select(*READ_PARAMS)
            .where(RelationshipsTable.user1 == user1)
            .where(RelationshipsTable.user2 == user2)
        )
        relationship = await self._database.fetch_one(select_stmt)

        assert relationship is not None
        return self._deserialize_relationship(relationship)

    async def fetch_all(
        self,
        user1: int,
        type: RelationshipType | None = None,
    ) -> list[Relationship]:
        """Fetch all of a user's relationships, optionally of a single type."""
        select_stmt = select(*READ_PARAMS).where(RelationshipsTable.user1 == user1)
        if type is not None:
            select_stmt = select_stmt.where(RelationshipsTable.type == type)

        relationships = await self._database.fetch_all(select_stmt)
        return [
            self._deserialize_relationship(relationship)
            for relationship in relationships
        ]

    async def fetch_one(self, user1: int, user2: int) -> Relationship | None:
        """Fetch the relationship between two users, if one exists."""
        select_stmt = (
            select(*READ_PARAMS)
            .where(RelationshipsTable.user1 == user1)
            .where(RelationshipsTable.user2 == user2)
        )
        relationship = await self._database.fetch_one(select_stmt)
        return (
            self._deserialize_relationship(relationship)
            if relationship is not None
            else None
        )

    async def delete(self, user1: int, user2: int) -> None:
        """Delete the relationship between two users."""
        delete_stmt = (
            delete(RelationshipsTable)
            .where(RelationshipsTable.user1 == user1)
            .where(RelationshipsTable.user2 == user2)
        )
        await self._database.execute(delete_stmt)
