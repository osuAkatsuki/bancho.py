from __future__ import annotations

import textwrap
from typing import Any
from typing import TypedDict
from typing import cast

import app.state.services
from app._typing import UNSET
from app._typing import _UnsetSentinel

# create table user_achievements
# (
# 	userid int not null,
# 	achid int not null,
# 	primary key (userid, achid)
# );

READ_PARAMS = textwrap.dedent(
    """\
        userid, achid
    """,
)


class UserAchievement(TypedDict):
    userid: int
    achid: int


async def create(user_id: int, achievement_id: int) -> UserAchievement:
    """Creates a new user achievement entry."""
    query = """\
        INSERT INTO user_achievements (userid, achid)
                VALUES (:user_id, :achievement_id)
    """
    params: dict[str, Any] = {
        "user_id": user_id,
        "achievement_id": achievement_id,
    }
    await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM user_achievements
         WHERE userid = :user_id
         AND achid = :achievement_id
    """
    user_achievement = await app.state.services.database.fetch_one(query, params)

    assert user_achievement is not None
    return cast(UserAchievement, dict(user_achievement._mapping))


async def fetch_many(
    user_id: int,
    page: int | _UnsetSentinel = UNSET,
    page_size: int | _UnsetSentinel = UNSET,
) -> list[UserAchievement]:
    """Fetch a list of user achievements."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM user_achievements
          WHERE userid = :user_id
    """
    params: dict[str, Any] = {
        "user_id": user_id,
    }

    if not isinstance(page, _UnsetSentinel) and not isinstance(
        page_size,
        _UnsetSentinel,
    ):
        query += """\
            LIMIT :limit
           OFFSET :offset
        """
        params["page_size"] = page_size
        params["offset"] = (page - 1) * page_size

    user_achievements = await app.state.services.database.fetch_all(query, params)
    return cast(list[UserAchievement], [dict(a._mapping) for a in user_achievements])


# TODO: delete?
