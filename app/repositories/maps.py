from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Enum
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import delete
from sqlalchemy import func
from sqlalchemy import insert
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.dialects.mysql import FLOAT
from sqlalchemy.dialects.mysql import TINYINT

from app._typing import UNSET
from app._typing import _UnsetSentinel
from app.adapters.database import Database
from app.adapters.database import MySQLRow
from app.repositories import Base


class MapServer(StrEnum):
    OSU = "osu!"
    PRIVATE = "private"


class MapsTable(Base):
    __tablename__ = "maps"

    server = Column(
        Enum(MapServer, name="server"),
        nullable=False,
        server_default="osu!",
        primary_key=True,
    )
    id = Column(Integer, nullable=False, primary_key=True)
    set_id = Column(Integer, nullable=False)
    status = Column(Integer, nullable=False)
    md5 = Column(String(32), nullable=False)
    artist = Column(String(128, collation="utf8"), nullable=False)
    title = Column(String(128, collation="utf8"), nullable=False)
    version = Column(String(128, collation="utf8"), nullable=False)
    creator = Column(String(19, collation="utf8"), nullable=False)
    filename = Column(String(256, collation="utf8"), nullable=False)
    last_update = Column(DateTime, nullable=False)
    total_length = Column(Integer, nullable=False)
    max_combo = Column(Integer, nullable=False)
    frozen = Column(TINYINT(1), nullable=False, server_default="0")
    plays = Column(Integer, nullable=False, server_default="0")
    passes = Column(Integer, nullable=False, server_default="0")
    mode = Column(TINYINT(1), nullable=False, server_default="0")
    bpm = Column(FLOAT(12, 2), nullable=False, server_default="0.00")
    cs = Column(FLOAT(4, 2), nullable=False, server_default="0.00")
    ar = Column(FLOAT(4, 2), nullable=False, server_default="0.00")
    od = Column(FLOAT(4, 2), nullable=False, server_default="0.00")
    hp = Column(FLOAT(4, 2), nullable=False, server_default="0.00")
    diff = Column(FLOAT(6, 3), nullable=False, server_default="0.000")

    __table_args__ = (
        Index("maps_set_id_index", "set_id"),
        Index("maps_status_index", "status"),
        Index("maps_filename_index", "filename"),
        Index("maps_plays_index", "plays"),
        Index("maps_mode_index", "mode"),
        Index("maps_frozen_index", "frozen"),
        Index("maps_md5_uindex", "md5", unique=True),
        Index("maps_id_uindex", "id", unique=True),
    )


READ_PARAMS = (
    MapsTable.id,
    MapsTable.server,
    MapsTable.set_id,
    MapsTable.status,
    MapsTable.md5,
    MapsTable.artist,
    MapsTable.title,
    MapsTable.version,
    MapsTable.creator,
    MapsTable.filename,
    MapsTable.last_update,
    MapsTable.total_length,
    MapsTable.max_combo,
    MapsTable.frozen,
    MapsTable.plays,
    MapsTable.passes,
    MapsTable.mode,
    MapsTable.bpm,
    MapsTable.cs,
    MapsTable.ar,
    MapsTable.od,
    MapsTable.hp,
    MapsTable.diff,
)


@dataclass(frozen=True, slots=True)
class Map:
    id: int
    server: str
    set_id: int
    status: int
    md5: str
    artist: str
    title: str
    version: str
    creator: str
    filename: str
    last_update: datetime
    total_length: int
    max_combo: int
    frozen: bool
    plays: int
    passes: int
    mode: int
    bpm: float
    cs: float
    ar: float
    od: float
    hp: float
    diff: float


@dataclass(frozen=True, slots=True)
class MapSetInfo:
    set_id: int
    artist: str
    title: str
    status: int
    creator: str
    last_update: datetime


class MapsRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def _deserialize_map(self, row: MySQLRow) -> Map:
        return Map(
            id=row["id"],
            server=str(row["server"]),
            set_id=row["set_id"],
            status=row["status"],
            md5=row["md5"],
            artist=row["artist"],
            title=row["title"],
            version=row["version"],
            creator=row["creator"],
            filename=row["filename"],
            last_update=row["last_update"],
            total_length=row["total_length"],
            max_combo=row["max_combo"],
            frozen=bool(row["frozen"]),
            plays=row["plays"],
            passes=row["passes"],
            mode=row["mode"],
            bpm=row["bpm"],
            cs=row["cs"],
            ar=row["ar"],
            od=row["od"],
            hp=row["hp"],
            diff=row["diff"],
        )

    def _deserialize_map_set_info(self, row: MySQLRow) -> MapSetInfo:
        return MapSetInfo(
            set_id=row["set_id"],
            artist=row["artist"],
            title=row["title"],
            status=row["status"],
            creator=row["creator"],
            last_update=row["last_update"],
        )

    async def create(
        self,
        id: int,
        server: str,
        set_id: int,
        status: int,
        md5: str,
        artist: str,
        title: str,
        version: str,
        creator: str,
        filename: str,
        last_update: datetime,
        total_length: int,
        max_combo: int,
        frozen: bool,
        plays: int,
        passes: int,
        mode: int,
        bpm: float,
        cs: float,
        ar: float,
        od: float,
        hp: float,
        diff: float,
    ) -> Map:
        """Create a new beatmap entry in the database."""
        insert_stmt = insert(MapsTable).values(
            id=id,
            server=server,
            set_id=set_id,
            status=status,
            md5=md5,
            artist=artist,
            title=title,
            version=version,
            creator=creator,
            filename=filename,
            last_update=last_update,
            total_length=total_length,
            max_combo=max_combo,
            frozen=frozen,
            plays=plays,
            passes=passes,
            mode=mode,
            bpm=bpm,
            cs=cs,
            ar=ar,
            od=od,
            hp=hp,
            diff=diff,
        )
        await self._database.execute(insert_stmt)

        select_stmt = select(*READ_PARAMS).where(MapsTable.id == id)
        map = await self._database.fetch_one(select_stmt)
        assert map is not None
        return self._deserialize_map(map)

    async def fetch_one(
        self,
        id: int | None = None,
        md5: str | None = None,
        filename: str | None = None,
    ) -> Map | None:
        """Fetch a beatmap entry from the database."""
        if id is None and md5 is None and filename is None:
            raise ValueError("Must provide at least one parameter.")

        select_stmt = select(*READ_PARAMS)
        if id is not None:
            select_stmt = select_stmt.where(MapsTable.id == id)
        if md5 is not None:
            select_stmt = select_stmt.where(MapsTable.md5 == md5)
        if filename is not None:
            select_stmt = select_stmt.where(MapsTable.filename == filename)

        map = await self._database.fetch_one(select_stmt)
        return self._deserialize_map(map) if map is not None else None

    async def fetch_set_info(
        self,
        *,
        set_id: int | None = None,
        map_id: int | None = None,
        md5: str | None = None,
    ) -> MapSetInfo | None:
        """Fetch beatmap set metadata by set id, map id, or map checksum."""
        if set_id is None and map_id is None and md5 is None:
            raise ValueError("Must provide at least one parameter.")

        select_stmt = (
            select(
                MapsTable.set_id,
                MapsTable.artist,
                MapsTable.title,
                MapsTable.status,
                MapsTable.creator,
                MapsTable.last_update,
            )
            .distinct()
            .select_from(MapsTable)
        )

        if set_id is not None:
            select_stmt = select_stmt.where(MapsTable.set_id == set_id)
        if map_id is not None:
            select_stmt = select_stmt.where(MapsTable.id == map_id)
        if md5 is not None:
            select_stmt = select_stmt.where(MapsTable.md5 == md5)

        bmapset = await self._database.fetch_one(select_stmt)
        return self._deserialize_map_set_info(bmapset) if bmapset is not None else None

    async def fetch_count(
        self,
        server: str | None = None,
        set_id: int | None = None,
        status: int | None = None,
        artist: str | None = None,
        creator: str | None = None,
        filename: str | None = None,
        mode: int | None = None,
        frozen: bool | None = None,
    ) -> int:
        """Fetch the number of maps in the database."""
        select_stmt = select(func.count().label("count")).select_from(MapsTable)
        if server is not None:
            select_stmt = select_stmt.where(MapsTable.server == server)
        if set_id is not None:
            select_stmt = select_stmt.where(MapsTable.set_id == set_id)
        if status is not None:
            select_stmt = select_stmt.where(MapsTable.status == status)
        if artist is not None:
            select_stmt = select_stmt.where(MapsTable.artist == artist)
        if creator is not None:
            select_stmt = select_stmt.where(MapsTable.creator == creator)
        if filename is not None:
            select_stmt = select_stmt.where(MapsTable.filename == filename)
        if mode is not None:
            select_stmt = select_stmt.where(MapsTable.mode == mode)
        if frozen is not None:
            select_stmt = select_stmt.where(MapsTable.frozen == frozen)

        rec = await self._database.fetch_one(select_stmt)
        assert rec is not None
        return int(rec["count"])

    async def fetch_many(
        self,
        server: str | None = None,
        set_id: int | None = None,
        status: int | None = None,
        artist: str | None = None,
        creator: str | None = None,
        filename: str | None = None,
        mode: int | None = None,
        frozen: bool | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> list[Map]:
        """Fetch a list of maps from the database."""
        select_stmt = select(*READ_PARAMS)
        if server is not None:
            select_stmt = select_stmt.where(MapsTable.server == server)
        if set_id is not None:
            select_stmt = select_stmt.where(MapsTable.set_id == set_id)
        if status is not None:
            select_stmt = select_stmt.where(MapsTable.status == status)
        if artist is not None:
            select_stmt = select_stmt.where(MapsTable.artist == artist)
        if creator is not None:
            select_stmt = select_stmt.where(MapsTable.creator == creator)
        if filename is not None:
            select_stmt = select_stmt.where(MapsTable.filename == filename)
        if mode is not None:
            select_stmt = select_stmt.where(MapsTable.mode == mode)
        if frozen is not None:
            select_stmt = select_stmt.where(MapsTable.frozen == frozen)

        if page is not None and page_size is not None:
            select_stmt = select_stmt.limit(page_size).offset((page - 1) * page_size)

        maps = await self._database.fetch_all(select_stmt)
        return [self._deserialize_map(map) for map in maps]

    async def partial_update(
        self,
        id: int,
        server: str | _UnsetSentinel = UNSET,
        set_id: int | _UnsetSentinel = UNSET,
        status: int | _UnsetSentinel = UNSET,
        md5: str | _UnsetSentinel = UNSET,
        artist: str | _UnsetSentinel = UNSET,
        title: str | _UnsetSentinel = UNSET,
        version: str | _UnsetSentinel = UNSET,
        creator: str | _UnsetSentinel = UNSET,
        filename: str | _UnsetSentinel = UNSET,
        last_update: datetime | _UnsetSentinel = UNSET,
        total_length: int | _UnsetSentinel = UNSET,
        max_combo: int | _UnsetSentinel = UNSET,
        frozen: bool | _UnsetSentinel = UNSET,
        plays: int | _UnsetSentinel = UNSET,
        passes: int | _UnsetSentinel = UNSET,
        mode: int | _UnsetSentinel = UNSET,
        bpm: float | _UnsetSentinel = UNSET,
        cs: float | _UnsetSentinel = UNSET,
        ar: float | _UnsetSentinel = UNSET,
        od: float | _UnsetSentinel = UNSET,
        hp: float | _UnsetSentinel = UNSET,
        diff: float | _UnsetSentinel = UNSET,
    ) -> Map | None:
        """Update a beatmap entry in the database."""
        update_stmt = update(MapsTable).where(MapsTable.id == id)
        if not isinstance(server, _UnsetSentinel):
            update_stmt = update_stmt.values(server=server)
        if not isinstance(set_id, _UnsetSentinel):
            update_stmt = update_stmt.values(set_id=set_id)
        if not isinstance(status, _UnsetSentinel):
            update_stmt = update_stmt.values(status=status)
        if not isinstance(md5, _UnsetSentinel):
            update_stmt = update_stmt.values(md5=md5)
        if not isinstance(artist, _UnsetSentinel):
            update_stmt = update_stmt.values(artist=artist)
        if not isinstance(title, _UnsetSentinel):
            update_stmt = update_stmt.values(title=title)
        if not isinstance(version, _UnsetSentinel):
            update_stmt = update_stmt.values(version=version)
        if not isinstance(creator, _UnsetSentinel):
            update_stmt = update_stmt.values(creator=creator)
        if not isinstance(filename, _UnsetSentinel):
            update_stmt = update_stmt.values(filename=filename)
        if not isinstance(last_update, _UnsetSentinel):
            update_stmt = update_stmt.values(last_update=last_update)
        if not isinstance(total_length, _UnsetSentinel):
            update_stmt = update_stmt.values(total_length=total_length)
        if not isinstance(max_combo, _UnsetSentinel):
            update_stmt = update_stmt.values(max_combo=max_combo)
        if not isinstance(frozen, _UnsetSentinel):
            update_stmt = update_stmt.values(frozen=frozen)
        if not isinstance(plays, _UnsetSentinel):
            update_stmt = update_stmt.values(plays=plays)
        if not isinstance(passes, _UnsetSentinel):
            update_stmt = update_stmt.values(passes=passes)
        if not isinstance(mode, _UnsetSentinel):
            update_stmt = update_stmt.values(mode=mode)
        if not isinstance(bpm, _UnsetSentinel):
            update_stmt = update_stmt.values(bpm=bpm)
        if not isinstance(cs, _UnsetSentinel):
            update_stmt = update_stmt.values(cs=cs)
        if not isinstance(ar, _UnsetSentinel):
            update_stmt = update_stmt.values(ar=ar)
        if not isinstance(od, _UnsetSentinel):
            update_stmt = update_stmt.values(od=od)
        if not isinstance(hp, _UnsetSentinel):
            update_stmt = update_stmt.values(hp=hp)
        if not isinstance(diff, _UnsetSentinel):
            update_stmt = update_stmt.values(diff=diff)

        await self._database.execute(update_stmt)

        select_stmt = select(*READ_PARAMS).where(MapsTable.id == id)
        map = await self._database.fetch_one(select_stmt)
        return self._deserialize_map(map) if map is not None else None

    async def delete_one(self, id: int) -> Map | None:
        """Delete a beatmap entry from the database."""
        select_stmt = select(*READ_PARAMS).where(MapsTable.id == id)
        map = await self._database.fetch_one(select_stmt)
        if map is None:
            return None

        delete_stmt = delete(MapsTable).where(MapsTable.id == id)
        await self._database.execute(delete_stmt)
        return self._deserialize_map(map)
