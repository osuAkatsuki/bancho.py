from __future__ import annotations

import textwrap
from typing import cast
from typing import TypedDict

import app.state.services
from app._typing import _UnsetSentinel
from app._typing import UNSET

# +--------------+------------------------+------+-----+---------+-------+
# | Field        | Type                   | Null | Key | Default | Extra |
# +--------------+------------------------+------+-----+---------+-------+
# | id           | int                    | NO   | PRI | NULL    |       |
# | server       | enum('osu!','private') | NO   |     | osu!    |       |
# | set_id       | int                    | NO   |     | NULL    |       |
# | status       | int                    | NO   |     | NULL    |       |
# | md5          | char(32)               | NO   | UNI | NULL    |       |
# | artist       | varchar(128)           | NO   |     | NULL    |       |
# | title        | varchar(128)           | NO   |     | NULL    |       |
# | version      | varchar(128)           | NO   |     | NULL    |       |
# | creator      | varchar(19)            | NO   |     | NULL    |       |
# | filename     | varchar(256)           | NO   |     | NULL    |       |
# | last_update  | datetime               | NO   |     | NULL    |       |
# | total_length | int                    | NO   |     | NULL    |       |
# | max_combo    | int                    | NO   |     | NULL    |       |
# | frozen       | tinyint(1)             | NO   |     | 0       |       |
# | plays        | int                    | NO   |     | 0       |       |
# | passes       | int                    | NO   |     | 0       |       |
# | mode         | tinyint(1)             | NO   |     | 0       |       |
# | bpm          | float(12,2)            | NO   |     | 0.00    |       |
# | cs           | float(4,2)             | NO   |     | 0.00    |       |
# | ar           | float(4,2)             | NO   |     | 0.00    |       |
# | od           | float(4,2)             | NO   |     | 0.00    |       |
# | hp           | float(4,2)             | NO   |     | 0.00    |       |
# | diff         | float(6,3)             | NO   |     | 0.000   |       |
# +--------------+------------------------+------+-----+---------+-------+

READ_PARAMS = textwrap.dedent(
    """\
        id, server, set_id, status, md5, artist, title, version, creator, filename,
        last_update, total_length, max_combo, frozen, plays, passes, mode, bpm, cs,
        ar, od, hp, diff
    """,
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
    last_update: str
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


class MapUpdateFields(TypedDict, total=False):
    server: str
    set_id: int
    status: int
    md5: str
    artist: str
    title: str
    version: str
    creator: str
    filename: str
    last_update: str
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
    last_update: str,
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
    query = f"""\
        INSERT INTO maps (id, server, set_id, status, md5, artist, title,
                          version, creator, filename, last_update,
                          total_length, max_combo, frozen, plays, passes,
                          mode, bpm, cs, ar, od, hp, diff)
             VALUES (:id, :server, :set_id, :status, :md5, :artist, :title,
                     :version, :creator, :filename, :last_update, :total_length,
                     :max_combo, :frozen, :plays, :passes, :mode, :bpm, :cs, :ar,
                     :od, :hp, :diff)
    """
    params = {
        "id": id,
        "server": server,
        "set_id": set_id,
        "status": status,
        "md5": md5,
        "artist": artist,
        "title": title,
        "version": version,
        "creator": creator,
        "filename": filename,
        "last_update": last_update,
        "total_length": total_length,
        "max_combo": max_combo,
        "frozen": frozen,
        "plays": plays,
        "passes": passes,
        "mode": mode,
        "bpm": bpm,
        "cs": cs,
        "ar": ar,
        "od": od,
        "hp": hp,
        "diff": diff,
    }
    rec_id = await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM maps
         WHERE id = :id
    """
    params = {
        "id": rec_id,
    }
    map = await app.state.services.database.fetch_one(query, params)

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

    query = f"""\
        SELECT {READ_PARAMS}
          FROM maps
         WHERE id = COALESCE(:id, id)
           AND md5 = COALESCE(:md5, md5)
           AND filename = COALESCE(:filename, filename)
    """
    params = {
        "id": id,
        "md5": md5,
        "filename": filename,
    }
    map = await app.state.services.database.fetch_one(query, params)

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
    query = """\
        SELECT COUNT(*) AS count
          FROM maps
        WHERE server = COALESCE(:server, server)
          AND set_id = COALESCE(:set_id, set_id)
          AND status = COALESCE(:status, status)
          AND artist = COALESCE(:artist, artist)
          AND creator = COALESCE(:creator, creator)
          AND filename = COALESCE(:filename, filename)
          AND mode = COALESCE(:mode, mode)
          AND frozen = COALESCE(:frozen, frozen)

    """
    params = {
        "server": server,
        "set_id": set_id,
        "status": status,
        "artist": artist,
        "creator": creator,
        "filename": filename,
        "mode": mode,
        "frozen": frozen,
    }
    rec = await app.state.services.database.fetch_one(query, params)
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
    query = f"""\
        SELECT {READ_PARAMS}
          FROM maps
         WHERE server = COALESCE(:server, server)
           AND set_id = COALESCE(:set_id, set_id)
           AND status = COALESCE(:status, status)
           AND artist = COALESCE(:artist, artist)
           AND creator = COALESCE(:creator, creator)
           AND filename = COALESCE(:filename, filename)
           AND mode = COALESCE(:mode, mode)
           AND frozen = COALESCE(:frozen, frozen)
    """
    params = {
        "server": server,
        "set_id": set_id,
        "status": status,
        "artist": artist,
        "creator": creator,
        "filename": filename,
        "mode": mode,
        "frozen": frozen,
    }

    if page is not None and page_size is not None:
        query += """\
            LIMIT :limit
           OFFSET :offset
        """
        params["limit"] = page_size
        params["offset"] = (page - 1) * page_size

    maps = await app.state.services.database.fetch_all(query, params)
    return cast(list[Map], [dict(m._mapping) for m in maps])


async def update(
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
    last_update: str | _UnsetSentinel = UNSET,
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
    update_fields: MapUpdateFields = {}
    if not isinstance(server, _UnsetSentinel):
        update_fields["server"] = server
    if not isinstance(set_id, _UnsetSentinel):
        update_fields["set_id"] = set_id
    if not isinstance(status, _UnsetSentinel):
        update_fields["status"] = status
    if not isinstance(md5, _UnsetSentinel):
        update_fields["md5"] = md5
    if not isinstance(artist, _UnsetSentinel):
        update_fields["artist"] = artist
    if not isinstance(title, _UnsetSentinel):
        update_fields["title"] = title
    if not isinstance(version, _UnsetSentinel):
        update_fields["version"] = version
    if not isinstance(creator, _UnsetSentinel):
        update_fields["creator"] = creator
    if not isinstance(filename, _UnsetSentinel):
        update_fields["filename"] = filename
    if not isinstance(last_update, _UnsetSentinel):
        update_fields["last_update"] = last_update
    if not isinstance(total_length, _UnsetSentinel):
        update_fields["total_length"] = total_length
    if not isinstance(max_combo, _UnsetSentinel):
        update_fields["max_combo"] = max_combo
    if not isinstance(frozen, _UnsetSentinel):
        update_fields["frozen"] = frozen
    if not isinstance(plays, _UnsetSentinel):
        update_fields["plays"] = plays
    if not isinstance(passes, _UnsetSentinel):
        update_fields["passes"] = passes
    if not isinstance(mode, _UnsetSentinel):
        update_fields["mode"] = mode
    if not isinstance(bpm, _UnsetSentinel):
        update_fields["bpm"] = bpm
    if not isinstance(cs, _UnsetSentinel):
        update_fields["cs"] = cs
    if not isinstance(ar, _UnsetSentinel):
        update_fields["ar"] = ar
    if not isinstance(od, _UnsetSentinel):
        update_fields["od"] = od
    if not isinstance(hp, _UnsetSentinel):
        update_fields["hp"] = hp
    if not isinstance(diff, _UnsetSentinel):
        update_fields["diff"] = diff

    query = f"""\
        UPDATE maps
           SET {",".join(f"{k} = COALESCE(:{k}, {k})" for k in update_fields)}
         WHERE id = :id
    """
    values = {"id": id} | update_fields
    await app.state.services.database.execute(query, values)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM maps
        WHERE id = :id
    """
    params = {
        "id": id,
    }
    map = await app.state.services.database.fetch_one(query, params)
    return cast(Map, dict(map._mapping)) if map is not None else None


async def delete(id: int) -> Map | None:
    """Delete a beatmap entry from the database."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM maps
        WHERE id = :id
    """
    params = {
        "id": id,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    if rec is None:
        return None

    query = """\
        DELETE FROM maps
              WHERE id = :id
    """
    params = {
        "id": id,
    }
    map = await app.state.services.database.execute(query, params)
    return cast(Map, dict(map._mapping)) if map is not None else None
