from __future__ import annotations

import textwrap
from collections.abc import Callable
from typing import Any
from typing import cast
from typing import TYPE_CHECKING
from typing import TypedDict

import app.state.services
from app._typing import _UnsetSentinel
from app._typing import UNSET

if TYPE_CHECKING:
    from app.objects.score import Score

# +-------+--------------+------+-----+---------+----------------+
# | Field | Type         | Null | Key | Default | Extra          |
# +-------+--------------+------+-----+---------+----------------+
# | id    | int          | NO   | PRI | NULL    | auto_increment |
# | file  | varchar(128) | NO   | UNI | NULL    |                |
# | name  | varchar(128) | NO   | UNI | NULL    |                |
# | desc  | varchar(256) | NO   | UNI | NULL    |                |
# | cond  | varchar(64)  | NO   |     | NULL    |                |
# +-------+--------------+------+-----+---------+----------------+

READ_PARAMS = textwrap.dedent(
    """\
        id, file, name, `desc`, cond
    """,
)


class Achievement(TypedDict):
    id: int
    file: str
    name: str
    desc: str
    cond: Callable[[Score, int], bool]


class AchievementUpdateFields(TypedDict, total=False):
    file: str
    name: str
    desc: str
    cond: str


async def create(
    file: str,
    name: str,
    desc: str,
    cond: str,
) -> Achievement:
    """Create a new achievement."""
    query = """\
        INSERT INTO achievements (file, name, desc, cond)
             VALUES (:file, :name, :desc, :cond)
    """
    params: dict[str, Any] = {
        "file": file,
        "name": name,
        "desc": desc,
        "cond": cond,
    }
    rec_id = await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM achievements
         WHERE id = :id
    """
    params = {
        "id": rec_id,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    assert rec is not None

    achievement = dict(rec._mapping)
    achievement["cond"] = eval(f'lambda score, mode_vn: {rec["cond"]}')
    return cast(Achievement, achievement)


async def fetch_one(
    id: int | None = None,
    name: str | None = None,
) -> Achievement | None:
    """Fetch a single achievement."""
    if id is None and name is None:
        raise ValueError("Must provide at least one parameter.")

    query = f"""\
        SELECT {READ_PARAMS}
          FROM achievements
         WHERE id = COALESCE(:id, id)
            OR name = COALESCE(:name, name)
    """
    params: dict[str, Any] = {
        "id": id,
        "name": name,
    }
    rec = await app.state.services.database.fetch_one(query, params)

    if rec is None:
        return None

    achievement = dict(rec._mapping)
    achievement["cond"] = eval(f'lambda score, mode_vn: {rec["cond"]}')
    return cast(Achievement, achievement)


async def fetch_count() -> int:
    """Fetch the number of achievements."""
    query = """\
        SELECT COUNT(*) AS count
          FROM achievements
    """
    params: dict[str, Any] = {}

    rec = await app.state.services.database.fetch_one(query, params)
    assert rec is not None
    return cast(int, rec._mapping["count"])


async def fetch_many(
    page: int | None = None,
    page_size: int | None = None,
) -> list[Achievement]:
    """Fetch a list of achievements."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM achievements
    """
    params: dict[str, Any] = {}

    if page is not None and page_size is not None:
        query += """\
            LIMIT :limit
           OFFSET :offset
        """
        params["page_size"] = page_size
        params["offset"] = (page - 1) * page_size

    records = await app.state.services.database.fetch_all(query, params)

    achievements: list[Achievement] = []

    for rec in records:
        achievement = dict(rec._mapping)
        achievement["cond"] = eval(f'lambda score, mode_vn: {rec["cond"]}')
        achievements.append(cast(Achievement, achievement))

    return achievements


async def update(
    id: int,
    file: str | _UnsetSentinel = UNSET,
    name: str | _UnsetSentinel = UNSET,
    desc: str | _UnsetSentinel = UNSET,
    cond: str | _UnsetSentinel = UNSET,
) -> Achievement | None:
    """Update an existing achievement."""
    update_fields: AchievementUpdateFields = {}
    if not isinstance(file, _UnsetSentinel):
        update_fields["file"] = file
    if not isinstance(name, _UnsetSentinel):
        update_fields["name"] = name
    if not isinstance(desc, _UnsetSentinel):
        update_fields["desc"] = desc
    if not isinstance(cond, _UnsetSentinel):
        update_fields["cond"] = cond

    query = f"""\
        UPDATE achievements
           SET {",".join(f"{k} = COALESCE(:{k}, {k})" for k in update_fields)}
         WHERE id = :id
    """
    values = {"id": id} | update_fields
    await app.state.services.database.execute(query, values)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM achievements
         WHERE id = :id
    """
    params: dict[str, Any] = {
        "id": id,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    assert rec is not None

    achievement = dict(rec._mapping)
    achievement["cond"] = eval(f'lambda score, mode_vn: {rec["cond"]}')
    return cast(Achievement, achievement)


async def delete(
    id: int,
) -> Achievement | None:
    """Delete an existing achievement."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM achievements
         WHERE id = :id
    """
    params: dict[str, Any] = {
        "id": id,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    if rec is None:
        return None

    query = """\
        DELETE FROM achievements
              WHERE id = :id
    """
    params = {
        "id": id,
    }
    await app.state.services.database.execute(query, params)

    achievement = dict(rec._mapping)
    achievement["cond"] = eval(f'lambda score, mode_vn: {rec["cond"]}')
    return cast(Achievement, achievement)
