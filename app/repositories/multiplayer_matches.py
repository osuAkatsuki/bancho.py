from __future__ import annotations

import json
import textwrap
from asyncio import TimerHandle
from collections import defaultdict
from enum import IntEnum
from enum import unique
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
from app.constants.osu_client_details import OsuStream
from app.constants.privileges import ClanPrivileges
from app.constants.privileges import Privileges
from app.utils import escape_enum
from app.utils import make_safe_name
from app.utils import pymysql_encode


@unique
@pymysql_encode(escape_enum)
class MatchWinConditions(IntEnum):
    SCORE = 0
    ACCURACY = 1
    COMBO = 2
    SCORE_V2 = 3


@unique
@pymysql_encode(escape_enum)
class MatchTeamTypes(IntEnum):
    HEAD_TO_HEAD = 0
    TAG_CO_OP = 1
    TEAM_VS = 2
    TAG_TEAM_VS = 3


@unique
@pymysql_encode(escape_enum)
class MatchTeams(IntEnum):
    NEUTRAL = 0
    BLUE = 1
    RED = 2


class StartingTimers(TypedDict):
    start: TimerHandle
    alerts: list[TimerHandle]
    time: float


class MutliplayerMatch(TypedDict):
    id: int
    name: str
    password: str
    has_public_history: bool
    map_name: str
    map_id: int
    map_md5: str
    host_id: int
    mode: GameMode
    mods: Mods
    win_condition: MatchWinConditions
    team_type: MatchTeamTypes
    freemods: bool
    seed: int
    in_progress: bool
    starting: StartingTimers | None
    tourney_pool_id: int | None
    is_scrimming: bool
    team_match_points: defaultdict[MatchTeams, int]
    ffa_match_points: defaultdict[int, int]
    bans: set[tuple[Mods, int]]
    winning_pts: int
    use_pp_scoring: bool
    tourney_client_user_ids: set[int]
    referees: set[int]

    # TODO: slots separately


class MultiplayerMatchUpdateFields(TypedDict, total=False):
    name: str | _UnsetSentinel
    password: str | _UnsetSentinel
    map_name: str | _UnsetSentinel
    map_id: int | _UnsetSentinel
    map_md5: str | _UnsetSentinel
    host_id: int | _UnsetSentinel
    mode: GameMode | _UnsetSentinel
    mods: Mods | _UnsetSentinel
    win_condition: MatchWinConditions | _UnsetSentinel
    team_type: MatchTeamTypes | _UnsetSentinel
    freemods: bool | _UnsetSentinel
    seed: int | _UnsetSentinel
    in_progress: bool | _UnsetSentinel
    starting: StartingTimers | _UnsetSentinel
    tourney_pool_id: int | _UnsetSentinel
    is_scrimming: bool | _UnsetSentinel
    team_match_points: defaultdict[MatchTeams, int] | _UnsetSentinel
    ffa_match_points: defaultdict[int, int] | _UnsetSentinel
    bans: set[tuple[Mods, int]] | _UnsetSentinel
    winning_pts: int | _UnsetSentinel
    use_pp_scoring: bool | _UnsetSentinel
    tourney_client_user_ids: set[int] | _UnsetSentinel
    referees: set[int] | _UnsetSentinel


@unique
@pymysql_encode(escape_enum)
class SlotStatus(IntEnum):
    open = 1
    locked = 2
    not_ready = 4
    ready = 8
    no_map = 16
    playing = 32
    complete = 64
    quit = 128

    # has_player = not_ready | ready | no_map | playing | complete


class MatchSlot(TypedDict):
    session_id: str | None
    status: SlotStatus
    team: MatchTeams
    mods: Mods
    loaded: bool
    skipped: bool


class MatchSlotUpdateFields(TypedDict, total=False):
    session_id: str | _UnsetSentinel
    status: SlotStatus | _UnsetSentinel
    team: MatchTeams | _UnsetSentinel
    mods: Mods | _UnsetSentinel
    loaded: bool | _UnsetSentinel
    skipped: bool | _UnsetSentinel


def serialize(match: MutliplayerMatch) -> str:
    """Serialize a match to a string."""
    serializable = {
        "id": match["id"],
        "name": match["name"],
        "password": match["password"],
        "has_public_history": match["has_public_history"],
        "map_name": match["map_name"],
        "map_id": match["map_id"],
        "map_md5": match["map_md5"],
        "host_id": match["host_id"],
        "mode": match["mode"].value,
        "mods": match["mods"].value,
        "win_condition": match["win_condition"].value,
        "team_type": match["team_type"].value,
        "freemods": match["freemods"],
        "seed": match["seed"],
        "in_progress": match["in_progress"],
        "starting": match["starting"],
        "tourney_pool_id": match["tourney_pool_id"],
        "is_scrimming": match["is_scrimming"],
        "team_match_points": match["team_match_points"],
        "ffa_match_points": match["ffa_match_points"],
        "bans": list(match["bans"]),
        "winning_pts": match["winning_pts"],
        "use_pp_scoring": match["use_pp_scoring"],
        "tourney_client_user_ids": list(match["tourney_client_user_ids"]),
        "referees": list(match["referees"]),
    }
    return json.dumps(serializable)


def deserialize(serialized: str) -> MutliplayerMatch:
    """Deserialize a match from a string."""
    deserialized = json.loads(serialized)
    match: MutliplayerMatch = {
        "id": deserialized["id"],
        "name": deserialized["name"],
        "password": deserialized["password"],
        "has_public_history": deserialized["has_public_history"],
        "map_name": deserialized["map_name"],
        "map_id": deserialized["map_id"],
        "map_md5": deserialized["map_md5"],
        "host_id": deserialized["host_id"],
        "mode": GameMode(deserialized["mode"]),
        "mods": Mods(deserialized["mods"]),
        "win_condition": MatchWinConditions(deserialized["win_condition"]),
        "team_type": MatchTeamTypes(deserialized["team_type"]),
        "freemods": deserialized["freemods"],
        "seed": deserialized["seed"],
        "in_progress": deserialized["in_progress"],
        "starting": deserialized["starting"],
        "tourney_pool_id": deserialized["tourney_pool_id"],
        "is_scrimming": deserialized["is_scrimming"],
        "team_match_points": defaultdict(int, deserialized["team_match_points"]),
        "ffa_match_points": defaultdict(int, deserialized["ffa_match_points"]),
        "bans": set(deserialized["bans"]),
        "winning_pts": deserialized["winning_pts"],
        "use_pp_scoring": deserialized["use_pp_scoring"],
        "tourney_client_user_ids": set(deserialized["tourney_client_user_ids"]),
        "referees": set(deserialized["referees"]),
    }
    return match


async def create(
    id: int,
    name: str,
    password: str,
    has_public_history: bool,
    map_name: str,
    map_id: int,
    map_md5: str,
    host_id: int,
    mode: GameMode,
    mods: Mods,
    win_condition: MatchWinConditions,
    team_type: MatchTeamTypes,
    freemods: bool,
    seed: int,
    in_progress: bool,
    starting: StartingTimers | None,
    tourney_pool_id: int | None,
    is_scrimming: bool,
    team_match_points: defaultdict[MatchTeams, int],
    ffa_match_points: defaultdict[int, int],
    bans: set[tuple[Mods, int]],
    winning_pts: int,
    use_pp_scoring: bool,
    tourney_client_user_ids: set[int],
    referees: set[int],
) -> MutliplayerMatch:
    """Create a new match in redis."""
    match: MutliplayerMatch = {
        "id": id,
        "name": name,
        "password": password,
        "has_public_history": has_public_history,
        "map_name": map_name,
        "map_id": map_id,
        "map_md5": map_md5,
        "host_id": host_id,
        "mode": mode,
        "mods": mods,
        "win_condition": win_condition,
        "team_type": team_type,
        "freemods": freemods,
        "seed": seed,
        "in_progress": in_progress,
        "starting": starting,
        "tourney_pool_id": tourney_pool_id,
        "is_scrimming": is_scrimming,
        "team_match_points": team_match_points,
        "ffa_match_points": ffa_match_points,
        "bans": bans,
        "winning_pts": winning_pts,
        "use_pp_scoring": use_pp_scoring,
        "tourney_client_user_ids": tourney_client_user_ids,
        "referees": referees,
    }
    await app.state.services.redis.set(
        name=f"bancho:multiplayer_matches:{id}",
        value=serialize(match),
    )
    return match


async def fetch_one(match_id: int) -> MutliplayerMatch | None:
    """Fetch a match from redis."""
    serialized = await app.state.services.redis.get(
        name=f"bancho:multiplayer_matches:{match_id}",
    )
    if serialized is None:
        return None
    return deserialize(serialized)


async def reserve_new_match_id() -> int:
    """Reserve a new match ID."""
    new_match_id = await app.state.services.redis.incr(
        name="bancho:multiplayer_match_ids",
    )
    return new_match_id


async def partial_update(
    match_id: int,
    name: str | _UnsetSentinel = UNSET,
    password: str | _UnsetSentinel = UNSET,
    map_name: str | _UnsetSentinel = UNSET,
    map_id: int | _UnsetSentinel = UNSET,
    map_md5: str | _UnsetSentinel = UNSET,
    host_id: int | _UnsetSentinel = UNSET,
    mode: GameMode | _UnsetSentinel = UNSET,
    mods: Mods | _UnsetSentinel = UNSET,
    win_condition: MatchWinConditions | _UnsetSentinel = UNSET,
    team_type: MatchTeamTypes | _UnsetSentinel = UNSET,
    freemods: bool | _UnsetSentinel = UNSET,
    seed: int | _UnsetSentinel = UNSET,
    in_progress: bool | _UnsetSentinel = UNSET,
    starting: StartingTimers | _UnsetSentinel = UNSET,
    tourney_pool_id: int | _UnsetSentinel = UNSET,
    is_scrimming: bool | _UnsetSentinel = UNSET,
    team_match_points: defaultdict[MatchTeams, int] | _UnsetSentinel = UNSET,
    ffa_match_points: defaultdict[int, int] | _UnsetSentinel = UNSET,
    bans: set[tuple[Mods, int]] | _UnsetSentinel = UNSET,
    winning_pts: int | _UnsetSentinel = UNSET,
    use_pp_scoring: bool | _UnsetSentinel = UNSET,
    tourney_client_user_ids: set[int] | _UnsetSentinel = UNSET,
    referees: set[int] | _UnsetSentinel = UNSET,
) -> MutliplayerMatch | None:
    """Update a match in redis."""
    pass


# TODO: slots should prolly live in another file
