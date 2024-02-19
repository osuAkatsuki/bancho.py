from __future__ import annotations

import json
import textwrap
from datetime import datetime
from enum import IntEnum
from enum import StrEnum
from typing import Any
from typing import TypedDict
from typing import cast

import app.state.services
from app._typing import UNSET
from app._typing import _UnsetSentinel
from app.constants.gamemodes import GameMode
from app.constants.grades import Grade
from app.constants.mods import Mods
from app.constants.osu_client_details import ClientDetails
from app.constants.privileges import ClanPrivileges
from app.constants.privileges import Privileges
from app.utils import make_safe_name


class GrantType(StrEnum):
    IMPLICIT = "implicit"


class ChannelMembership(TypedDict):
    session_id: str
    channel_name: str
    grant_type: GrantType
    created_at: datetime


def serialize(channel_membership: ChannelMembership) -> str:
    """Serialize a channel membership to a string."""
    serializable = {
        "session_id": channel_membership["session_id"],
        "channel_name": channel_membership["channel_name"],
        "grant_type": channel_membership["grant_type"],
        "created_at": channel_membership["created_at"].isoformat(),
    }
    return json.dumps(serializable)


def deserialize(serialized: str) -> ChannelMembership:
    """Deserialize a channel membership from a string."""
    deserialized = json.loads(serialized)
    return {
        "session_id": deserialized["session_id"],
        "channel_name": deserialized["channel_name"],
        "grant_type": GrantType(deserialized["grant_type"]),
        "created_at": datetime.fromisoformat(deserialized["created_at"]),
    }


async def create(
    session_id: str,
    channel_name: str,
    grant_type: GrantType,
) -> ChannelMembership:
    """Create a new channel membership in redis."""
    membership: ChannelMembership = {
        "session_id": session_id,
        "channel_name": channel_name,
        "grant_type": grant_type,
        "created_at": datetime.utcnow(),
    }
    await app.state.services.redis.hset(  # type: ignore[awaitable]
        name=f"bancho:channel_memberships:{channel_name}",
        key=session_id,
        value=serialize(membership),
    )
    return membership


async def fetch_all(channel_name: str) -> list[ChannelMembership]:
    """Fetch all channel memberships from redis."""
    cursor = None
    channel_memberships = []

    while cursor != 0:
        cursor, serialized_memberships = await app.state.services.redis.hscan(
            f"bancho:channel_memberships:{channel_name}",
            cursor=cursor or 0,
        )
        for serialized in serialized_memberships:
            channel_membership = deserialize(serialized)
            channel_memberships.append(channel_membership)

    return channel_memberships


async def revoke(
    session_id: str,
    channel_name: str,
) -> ChannelMembership | None:
    """Remove a channel membership from redis."""
    serialized = await app.state.services.redis.hget(  # type: ignore[awaitable]
        f"bancho:channel_memberships:{channel_name}",
        session_id,
    )
    if serialized is None:
        return None
    await app.state.services.redis.hdel(  # type: ignore[awaitable]
        f"bancho:channel_memberships:{channel_name}",
        [session_id],
    )
    return deserialize(serialized)
