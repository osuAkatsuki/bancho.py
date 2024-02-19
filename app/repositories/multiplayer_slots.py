from __future__ import annotations

import json
from asyncio import TimerHandle
from collections import defaultdict
from enum import IntEnum
from enum import unique
from typing import TypedDict

import app.state.services
from app._typing import UNSET
from app._typing import _UnsetSentinel
from app.constants.mods import Mods
from app.constants.multiplayer import MatchTeams
from app.constants.multiplayer import SlotStatus


class MatchSlot(TypedDict):
    match_id: int
    slot_id: int
    user_id: int
    session_id: str
    status: SlotStatus
    team: MatchTeams
    mods: Mods
    loaded: bool
    skipped: bool


class MatchSlotUpdateFields(TypedDict, total=False):
    status: SlotStatus | _UnsetSentinel
    team: MatchTeams | _UnsetSentinel
    mods: Mods | _UnsetSentinel
    loaded: bool | _UnsetSentinel
    skipped: bool | _UnsetSentinel


def serialize(slot: MatchSlot) -> str:
    """Serialize a slot to a string."""
    serializable = {
        "match_id": slot["match_id"],
        "slot_id": slot["slot_id"],
        "user_id": slot["user_id"],
        "session_id": slot["session_id"],
        "status": slot["status"].value,
        "team": slot["team"].value,
        "mods": slot["mods"].value,
        "loaded": slot["loaded"],
        "skipped": slot["skipped"],
    }
    return json.dumps(serializable)


def deserialize(serialized: str) -> MatchSlot:
    """Deserialize a slot from a string."""
    deserialized = json.loads(serialized)
    match_slot: MatchSlot = {
        "match_id": deserialized["match_id"],
        "slot_id": deserialized["slot_id"],
        "user_id": deserialized["user_id"],
        "session_id": deserialized["session_id"],
        "status": SlotStatus(deserialized["status"]),
        "team": MatchTeams(deserialized["team"]),
        "mods": Mods(deserialized["mods"]),
        "loaded": deserialized["loaded"],
        "skipped": deserialized["skipped"],
    }
    return match_slot


def make_redis_key(match_id: int) -> str:
    return f"bancho:multiplayer_matches:{match_id}:slots"


def make_match_ids_redis_key(match_id: int) -> str:
    return f"bancho:multiplayer_matches:{match_id}:slot_ids"


async def reserve_match_slot_id(match_id: int) -> int | None:
    """Reserve a new slot id for a match."""
    match_slots = await app.state.services.redis.hgetall(  # type: ignore[awaitable]
        make_redis_key(match_id),
    )
    for slot_id in range(16):
        if str(slot_id) not in match_slots:
            return slot_id
    return None


async def create(
    match_id: int,
    slot_id: int,
    user_id: int,
    session_id: str,
    status: SlotStatus,
    team: MatchTeams,
    mods: Mods,
    loaded: bool,
    skipped: bool,
) -> MatchSlot:
    """Create a new slot in redis."""
    match_slot: MatchSlot = {
        "match_id": match_id,
        "slot_id": slot_id,
        "user_id": user_id,
        "session_id": session_id,
        "status": status,
        "team": team,
        "mods": mods,
        "loaded": loaded,
        "skipped": skipped,
    }
    await app.state.services.redis.hset(  # type: ignore[awaitable]
        name=make_redis_key(match_id),
        key=str(slot_id),
        value=serialize(match_slot),
    )
    return match_slot


async def fetch_one(match_id: int, slot_id: int) -> MatchSlot | None:
    """Fetch a slot from redis."""
    serialized = await app.state.services.redis.hget(  # type: ignore[awaitable]
        name=make_redis_key(match_id),
        key=str(slot_id),
    )
    if serialized is None:
        return None
    return deserialize(serialized)


async def fetch_user_slot_in_match(match_id: int, user_id: int) -> MatchSlot | None:
    """Fetch a user's slot in a match."""
    serialized = await app.state.services.redis.hgetall(  # type: ignore[awaitable]
        name=make_redis_key(match_id),
    )
    for serialized_slot in serialized.values():
        slot = deserialize(serialized_slot)
        if slot["user_id"] == user_id:
            return slot
    return None


async def fetch_all_for_match(match_id: int) -> dict[str, MatchSlot]:
    """Fetch all slots from redis."""
    serialized = await app.state.services.redis.hgetall(  # type: ignore[awaitable]
        name=make_redis_key(match_id),
    )
    return {
        slot_id: deserialize(serialized) for slot_id, serialized in serialized.items()
    }


async def partial_update(
    match_id: int,
    slot_id: int,
    status: SlotStatus | _UnsetSentinel = UNSET,
    team: MatchTeams | _UnsetSentinel = UNSET,
    mods: Mods | _UnsetSentinel = UNSET,
    loaded: bool | _UnsetSentinel = UNSET,
    skipped: bool | _UnsetSentinel = UNSET,
) -> MatchSlot | None:
    """Partially update a slot in redis."""
    serialized = await app.state.services.redis.hget(  # type: ignore[awaitable]
        name=make_redis_key(match_id),
        key=str(slot_id),
    )
    if serialized is None:
        return None

    match_slot = deserialize(serialized)

    update_fields: MatchSlotUpdateFields = {}
    if not isinstance(status, _UnsetSentinel):
        update_fields["status"] = status
    if not isinstance(team, _UnsetSentinel):
        update_fields["team"] = team
    if not isinstance(mods, _UnsetSentinel):
        update_fields["mods"] = mods
    if not isinstance(loaded, _UnsetSentinel):
        update_fields["loaded"] = loaded
    if not isinstance(skipped, _UnsetSentinel):
        update_fields["skipped"] = skipped

    updated_match_slot: MatchSlot = {**match_slot, **update_fields}

    await app.state.services.redis.hset(  # type: ignore[awaitable]
        name=make_redis_key(match_id),
        key=str(slot_id),
        value=serialize(updated_match_slot),
    )
    return updated_match_slot


async def delete(match_id: int, slot_id: int) -> MatchSlot | None:
    """Delete a slot from redis."""
    serialized = await app.state.services.redis.hget(  # type: ignore[awaitable]
        name=make_redis_key(match_id),
        key=str(slot_id),
    )
    if serialized is None:
        return None

    await app.state.services.redis.hdel(  # type: ignore[awaitable]
        make_redis_key(match_id),
        [str(slot_id)],
    )
    return deserialize(serialized)
