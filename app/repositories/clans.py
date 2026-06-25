from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import delete
from sqlalchemy import func
from sqlalchemy import insert
from sqlalchemy import select
from sqlalchemy import update

from app._typing import UNSET
from app._typing import _UnsetSentinel
from app.adapters.database import Database
from app.adapters.database import MySQLRow
from app.repositories import Base


class ClansTable(Base):
    __tablename__ = "clans"

    id = Column("id", Integer, primary_key=True, nullable=False, autoincrement=True)
    name = Column("name", String(16, collation="utf8"), nullable=False)
    tag = Column("tag", String(6, collation="utf8"), nullable=False)
    owner = Column("owner", Integer, nullable=False)
    created_at = Column("created_at", DateTime, nullable=False)

    __table_args__ = (
        Index("clans_name_uindex", name, unique=False),
        Index("clans_owner_uindex", owner, unique=True),
        Index("clans_tag_uindex", tag, unique=True),
    )


READ_PARAMS = (
    ClansTable.id,
    ClansTable.name,
    ClansTable.tag,
    ClansTable.owner,
    ClansTable.created_at,
)


@dataclass(frozen=True, slots=True)
class Clan:
    id: int
    name: str
    tag: str
    owner: int
    created_at: datetime


class ClansRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def _serialize_clan(self, clan: Clan) -> MySQLRow:
        return {
            "id": clan.id,
            "name": clan.name,
            "tag": clan.tag,
            "owner": clan.owner,
            "created_at": clan.created_at,
        }

    def _deserialize_clan(self, row: MySQLRow) -> Clan:
        return Clan(
            id=row["id"],
            name=row["name"],
            tag=row["tag"],
            owner=row["owner"],
            created_at=row["created_at"],
        )

    async def create(
        self,
        name: str,
        tag: str,
        owner: int,
    ) -> Clan:
        """Create a new clan in the database."""
        insert_stmt = insert(ClansTable).values(
            name=name,
            tag=tag,
            owner=owner,
            created_at=func.now(),
        )
        rec_id = await self._database.execute(insert_stmt)

        select_stmt = select(*READ_PARAMS).where(ClansTable.id == rec_id)
        clan = await self._database.fetch_one(select_stmt)

        assert clan is not None
        return self._deserialize_clan(clan)

    async def fetch_one(
        self,
        id: int | None = None,
        name: str | None = None,
        tag: str | None = None,
        owner: int | None = None,
    ) -> Clan | None:
        """Fetch a single clan from the database."""
        if id is None and name is None and tag is None and owner is None:
            raise ValueError("Must provide at least one parameter.")

        select_stmt = select(*READ_PARAMS)

        if id is not None:
            select_stmt = select_stmt.where(ClansTable.id == id)
        if name is not None:
            select_stmt = select_stmt.where(ClansTable.name == name)
        if tag is not None:
            select_stmt = select_stmt.where(ClansTable.tag == tag)
        if owner is not None:
            select_stmt = select_stmt.where(ClansTable.owner == owner)

        clan = await self._database.fetch_one(select_stmt)
        return self._deserialize_clan(clan) if clan is not None else None

    async def fetch_count(self) -> int:
        """Fetch the number of clans in the database."""
        select_stmt = select(func.count().label("count")).select_from(ClansTable)
        rec = await self._database.fetch_one(select_stmt)

        assert rec is not None
        return int(rec["count"])

    async def fetch_many(
        self,
        page: int | None = None,
        page_size: int | None = None,
    ) -> list[Clan]:
        """Fetch many clans from the database."""
        select_stmt = select(*READ_PARAMS)
        if page is not None and page_size is not None:
            select_stmt = select_stmt.limit(page_size).offset((page - 1) * page_size)

        clans = await self._database.fetch_all(select_stmt)
        return [self._deserialize_clan(clan) for clan in clans]

    async def partial_update(
        self,
        id: int,
        name: str | _UnsetSentinel = UNSET,
        tag: str | _UnsetSentinel = UNSET,
        owner: int | _UnsetSentinel = UNSET,
    ) -> Clan | None:
        """Update a clan in the database."""
        update_stmt = update(ClansTable).where(ClansTable.id == id)
        if not isinstance(name, _UnsetSentinel):
            update_stmt = update_stmt.values(name=name)
        if not isinstance(tag, _UnsetSentinel):
            update_stmt = update_stmt.values(tag=tag)
        if not isinstance(owner, _UnsetSentinel):
            update_stmt = update_stmt.values(owner=owner)

        await self._database.execute(update_stmt)

        select_stmt = select(*READ_PARAMS).where(ClansTable.id == id)
        clan = await self._database.fetch_one(select_stmt)
        return self._deserialize_clan(clan) if clan is not None else None

    async def delete_one(self, id: int) -> Clan | None:
        """Delete a clan from the database."""
        select_stmt = select(*READ_PARAMS).where(ClansTable.id == id)
        clan = await self._database.fetch_one(select_stmt)
        if clan is None:
            return None

        delete_stmt = delete(ClansTable).where(ClansTable.id == id)
        await self._database.execute(delete_stmt)
        return self._deserialize_clan(clan)
