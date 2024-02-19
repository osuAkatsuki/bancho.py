from __future__ import annotations

import textwrap
from enum import StrEnum
from typing import Any
from typing import TypedDict
from typing import cast

import app.state.services
from app._typing import UNSET
from app._typing import _UnsetSentinel

# +-------+------------------------+------+-----+---------+-------+
# | Field | Type                   | Null | Key | Default | Extra |
# +-------+------------------------+------+-----+---------+-------+
# | user1 | int                    | NO   | PRI | NULL    |       |
# | user2 | int                    | NO   | PRI | NULL    |       |
# | type  | enum('friend','block') | NO   |     | NULL    |       |
# +-------+------------------------+------+-----+---------+-------+


READ_PARAMS = textwrap.dedent(
    """\
        user1, user2, type
    """,
)


class RelationshipType(StrEnum):
    FRIEND = "friend"
    BLOCK = "block"


class Relationship(TypedDict):
    user1: int
    user2: int
    type: RelationshipType


async def create(
    user1: int,
    user2: int,
    type: RelationshipType,
) -> Relationship:
    """Create a new relationship in the database."""
    query = """\
        INSERT INTO relationships (user1, user2, type)
             VALUES (:user1, :user2, :type)
    """
    params: dict[str, Any] = {
        "user1": user1,
        "user2": user2,
        "type": type,
    }
    await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM relationships
         WHERE user1 = :user1
           AND user2 = :user2
    """
    params = {
        "user1": user1,
        "user2": user2,
    }
    row = await app.state.services.database.fetch_one(query, params)
    assert row is not None
    return cast(Relationship, dict(row._mapping))


async def fetch_related_users(
    user_id: int,
    relationship_type: RelationshipType,
) -> list[Relationship]:
    """Get all friends of a user."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM relationships
         WHERE user1 = :user_id
           AND type = :relationship_type
    """
    params: dict[str, Any] = {
        "user_id": user_id,
        "relationship_type": relationship_type,
    }
    rows = await app.state.services.database.fetch_all(query, params)
    return cast(list[Relationship], [dict(row._mapping) for row in rows])
