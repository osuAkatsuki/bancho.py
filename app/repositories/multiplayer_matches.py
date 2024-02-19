from __future__ import annotations

import json
from asyncio import TimerHandle
from collections import defaultdict
from typing import TypedDict

import app.state.services
from app._typing import UNSET
from app._typing import _UnsetSentinel
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.constants.multiplayer import MatchTeams
from app.constants.multiplayer import MatchTeamTypes
from app.constants.multiplayer import MatchWinConditions


class StartingTimers(TypedDict):
    start: TimerHandle
    alerts: list[TimerHandle]
    time: float


class MultiplayerMatch(TypedDict):
    match_id: int
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


def serialize(match: MultiplayerMatch) -> str:
    """Serialize a match to a string."""
    serializable = {
        "match_id": match["match_id"],
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


def deserialize(serialized: str) -> MultiplayerMatch:
    """Deserialize a match from a string."""
    deserialized = json.loads(serialized)
    match: MultiplayerMatch = {
        "match_id": deserialized["match_id"],
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


def make_redis_key(match_id: int) -> str:
    return f"bancho:multiplayer_matches:{match_id}"


async def create(
    match_id: int,
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
) -> MultiplayerMatch:
    """Create a new match in redis."""
    match: MultiplayerMatch = {
        "match_id": match_id,
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
        name=f"bancho:multiplayer_matches:{match_id}",
        value=serialize(match),
    )
    return match


async def fetch_one(match_id: int) -> MultiplayerMatch | None:
    """Fetch a match from redis."""
    serialized = await app.state.services.redis.get(
        name=make_redis_key(match_id),
    )
    if serialized is None:
        return None
    return deserialize(serialized)


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
) -> MultiplayerMatch | None:
    """Update a match in redis."""
    raw_multiplayer_match = await app.state.services.redis.get(
        name=make_redis_key(match_id),
    )
    if raw_multiplayer_match is None:
        return None

    multiplayer_match = deserialize(raw_multiplayer_match)

    update_fields: MultiplayerMatchUpdateFields = {}

    if not isinstance(name, _UnsetSentinel):
        update_fields["name"] = name
    if not isinstance(password, _UnsetSentinel):
        update_fields["password"] = password
    if not isinstance(map_name, _UnsetSentinel):
        update_fields["map_name"] = map_name
    if not isinstance(map_id, _UnsetSentinel):
        update_fields["map_id"] = map_id
    if not isinstance(map_md5, _UnsetSentinel):
        update_fields["map_md5"] = map_md5
    if not isinstance(host_id, _UnsetSentinel):
        update_fields["host_id"] = host_id
    if not isinstance(mode, _UnsetSentinel):
        update_fields["mode"] = mode
    if not isinstance(mods, _UnsetSentinel):
        update_fields["mods"] = mods
    if not isinstance(win_condition, _UnsetSentinel):
        update_fields["win_condition"] = win_condition
    if not isinstance(team_type, _UnsetSentinel):
        update_fields["team_type"] = team_type
    if not isinstance(freemods, _UnsetSentinel):
        update_fields["freemods"] = freemods
    if not isinstance(seed, _UnsetSentinel):
        update_fields["seed"] = seed
    if not isinstance(in_progress, _UnsetSentinel):
        update_fields["in_progress"] = in_progress
    if not isinstance(starting, _UnsetSentinel):
        update_fields["starting"] = starting
    if not isinstance(tourney_pool_id, _UnsetSentinel):
        update_fields["tourney_pool_id"] = tourney_pool_id
    if not isinstance(is_scrimming, _UnsetSentinel):
        update_fields["is_scrimming"] = is_scrimming
    if not isinstance(team_match_points, _UnsetSentinel):
        update_fields["team_match_points"] = team_match_points
    if not isinstance(ffa_match_points, _UnsetSentinel):
        update_fields["ffa_match_points"] = ffa_match_points
    if not isinstance(bans, _UnsetSentinel):
        update_fields["bans"] = bans
    if not isinstance(winning_pts, _UnsetSentinel):
        update_fields["winning_pts"] = winning_pts
    if not isinstance(use_pp_scoring, _UnsetSentinel):
        update_fields["use_pp_scoring"] = use_pp_scoring
    if not isinstance(tourney_client_user_ids, _UnsetSentinel):
        update_fields["tourney_client_user_ids"] = tourney_client_user_ids
    if not isinstance(referees, _UnsetSentinel):
        update_fields["referees"] = referees

    updated_multiplayer_match: MultiplayerMatch = {**multiplayer_match, **update_fields}

    await app.state.services.redis.set(
        name=make_redis_key(match_id),
        value=serialize(updated_multiplayer_match),
    )
    return updated_multiplayer_match


async def delete(match_id: int) -> MultiplayerMatch | None:
    """Delete a match from redis."""
    serialized = await app.state.services.redis.get(
        name=make_redis_key(match_id),
    )
    if serialized is None:
        return None

    await app.state.services.redis.delete(
        make_redis_key(match_id),
    )
    return deserialize(serialized)


# match ids


def make_match_ids_redis_key() -> str:
    return "bancho:multiplayer_match_ids"


async def reserve_new_match_id() -> int:
    """Reserve a new match ID."""
    new_match_id = await app.state.services.redis.incr(
        name=make_match_ids_redis_key(),
    )
    return new_match_id
