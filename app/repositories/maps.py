from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TypedDict
from typing import cast

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

import app.state.services
from app._typing import UNSET
from app._typing import _UnsetSentinel
from app.repositories import DIALECT
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


class Map(TypedDict):
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


async def create(
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
    compiled = insert_stmt.compile(dialect=DIALECT)
    rec_id = await app.state.services.database.execute(str(compiled), compiled.params)

    select_stmt = select(READ_PARAMS).where(MapsTable.id == rec_id)
    compiled = select_stmt.compile(dialect=DIALECT)
    map = await app.state.services.database.fetch_one(str(compiled), compiled.params)
    assert map is not None
    return cast(Map, dict(map._mapping))


async def fetch_one(
    id: int | None = None,
    md5: str | None = None,
    filename: str | None = None,
) -> Map | None:
    """Fetch a beatmap entry from the database."""
    if id is None and md5 is None and filename is None:
        raise ValueError("Must provide at least one parameter.")

    select_stmt = select(READ_PARAMS)
    if id is not None:
        select_stmt = select_stmt.where(MapsTable.id == id)
    if md5 is not None:
        select_stmt = select_stmt.where(MapsTable.md5 == md5)
    if filename is not None:
        select_stmt = select_stmt.where(MapsTable.filename == filename)
    compiled = select_stmt.compile(dialect=DIALECT)
    map = await app.state.services.database.fetch_one(str(compiled), compiled.params)
    return cast(Map, dict(map._mapping)) if map is not None else None


async def fetch_count(
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
    compiled = select_stmt.compile(dialect=DIALECT)
    rec = await app.state.services.database.fetch_one(str(compiled), compiled.params)
    assert rec is not None
    return cast(int, rec._mapping["count"])


async def fetch_many(
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
    select_stmt = select(READ_PARAMS)
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
    compiled = select_stmt.compile(dialect=DIALECT)
    maps = await app.state.services.database.fetch_all(str(compiled), compiled.params)
    return cast(list[Map], [dict(m._mapping) for m in maps])


async def partial_update(
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

    compiled = update_stmt.compile(dialect=DIALECT)
    await app.state.services.database.execute(str(compiled), compiled.params)

    select_stmt = select(READ_PARAMS).where(MapsTable.id == id)
    compiled = select_stmt.compile(dialect=DIALECT)
    map = await app.state.services.database.fetch_one(str(compiled), compiled.params)
    return cast(Map, dict(map._mapping)) if map is not None else None


async def delete_one(id: int) -> Map | None:
    """Delete a beatmap entry from the database."""
    select_stmt = select(READ_PARAMS).where(MapsTable.id == id)
    compiled = select_stmt.compile(dialect=DIALECT)
    map = await app.state.services.database.fetch_one(str(compiled), compiled.params)
    if map is None:
        return None

    delete_stmt = delete(MapsTable).where(MapsTable.id == id)
    compiled = delete_stmt.compile(dialect=DIALECT)
    await app.state.services.database.execute(str(compiled), compiled.params)
    return cast(Map, dict(map._mapping))
