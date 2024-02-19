from __future__ import annotations

import json
import textwrap
from enum import IntEnum
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
from app.utils import make_safe_name


class Action(IntEnum):
    """The client's current app.state."""

    Idle = 0
    Afk = 1
    Playing = 2
    Editing = 3
    Modding = 4
    Multiplayer = 5
    Watching = 6
    Unknown = 7
    Testing = 8
    Submitting = 9
    Paused = 10
    Lobby = 11
    Multiplaying = 12
    OsuDirect = 13


class PresenceFilter(IntEnum):
    """osu! client side filter for which users the player can see."""

    Nil = 0
    All = 1
    Friends = 2


class Status(TypedDict):
    """The current status of a player."""

    action: Action
    info_text: str
    map_md5: str
    mods: Mods
    mode: GameMode
    map_id: int


class LastNp(TypedDict):
    beatmap_id: int
    mode_vn: int
    mods: Mods | None
    timeout: float


class OsuSession(TypedDict):
    user_id: int
    name: str
    priv: Privileges
    pw_bcrypt: bytes | None
    session_id: str
    clan_id: int | None
    clan_priv: ClanPrivileges | None
    geoloc: app.state.services.Geolocation
    utc_offset: int
    pm_private: bool
    silence_end: int
    donor_end: int
    client_details: ClientDetails | None
    login_time: float
    last_recv_time: float
    is_bot_client: bool
    is_tourney_client: bool
    api_key: str | None
    away_msg: str | None
    in_lobby: bool
    status: Status
    friend_ids: set[int]
    blocked_ids: set[int]
    channel_ids: set[int]
    spectator_session_ids: set[str]
    spectating_session_id: str | None
    match_id: int | None
    pres_filter: PresenceFilter
    recent_score_ids: dict[GameMode, int | None]
    last_np: LastNp | None


class OsuSessionUpdateFields(TypedDict, total=False):
    name: str
    priv: Privileges
    pw_bcrypt: bytes | None
    clan_id: int | None
    clan_priv: ClanPrivileges | None
    geoloc: app.state.services.Geolocation
    pm_private: bool
    silence_end: int
    donor_end: int
    last_recv_time: float
    api_key: str | None
    away_msg: str | None
    in_lobby: bool
    status: Status
    friend_ids: set[int]
    blocked_ids: set[int]
    channel_ids: set[int]
    spectator_session_ids: set[str]
    spectating_session_id: str | None
    match_id: int | None
    pres_filter: PresenceFilter
    recent_score_ids: dict[GameMode, int | None]
    last_np: LastNp | None


def serialize(osu_session: OsuSession) -> str:
    """Serialize an osu! session to a string."""
    serializable = {
        "user_id": osu_session["user_id"],
        "name": osu_session["name"],
        "priv": osu_session["priv"].value,
        "pw_bcrypt": (
            osu_session["pw_bcrypt"].decode() if osu_session["pw_bcrypt"] else None
        ),
        "session_id": osu_session["session_id"],
        "clan_id": osu_session["clan_id"],
        "clan_priv": (
            osu_session["clan_priv"].value if osu_session["clan_priv"] else None
        ),
        "geoloc": osu_session["geoloc"],
        "utc_offset": osu_session["utc_offset"],
        "pm_private": osu_session["pm_private"],
        "silence_end": osu_session["silence_end"],
        "donor_end": osu_session["donor_end"],
        "client_details": osu_session["client_details"],
        "login_time": osu_session["login_time"],
        "last_recv_time": osu_session["last_recv_time"],
        "is_bot_client": osu_session["is_bot_client"],
        "is_tourney_client": osu_session["is_tourney_client"],
        "api_key": osu_session["api_key"],
        "away_msg": osu_session["away_msg"],
        "in_lobby": osu_session["in_lobby"],
        "status": {
            "action": osu_session["status"]["action"].value,
            "info_text": osu_session["status"]["info_text"],
            "map_md5": osu_session["status"]["map_md5"],
            "mods": osu_session["status"]["mods"].value,
            "mode": osu_session["status"]["mode"].value,
            "map_id": osu_session["status"]["map_id"],
        },
        "friend_ids": list(osu_session["friend_ids"]),
        "blocked_ids": list(osu_session["blocked_ids"]),
        "channel_ids": osu_session["channel_ids"],
        "spectator_session_ids": osu_session["spectator_session_ids"],
        "spectating_session_id": osu_session["spectating_session_id"],
        "match_id": osu_session["match_id"],
        "pres_filter": osu_session["pres_filter"].value,
        "recent_scores": {
            mode: score_id for mode, score_id in osu_session["recent_score_ids"].items()
        },
        "last_np": osu_session["last_np"],
    }
    return json.dumps(serializable)


def deserialize(serialized: str) -> OsuSession:
    """Deserialize an osu! session from a string."""
    deserialized = json.loads(serialized)
    osu_session: OsuSession = {
        "user_id": deserialized["user_id"],
        "name": deserialized["name"],
        "priv": Privileges(deserialized["priv"]),
        "pw_bcrypt": (
            deserialized["pw_bcrypt"].encode() if deserialized["pw_bcrypt"] else None
        ),
        "session_id": deserialized["session_id"],
        "clan_id": deserialized["clan_id"],
        "clan_priv": (
            ClanPrivileges(deserialized["clan_priv"])
            if deserialized["clan_priv"]
            else None
        ),
        "geoloc": deserialized["geoloc"],
        "utc_offset": deserialized["utc_offset"],
        "pm_private": deserialized["pm_private"],
        "silence_end": deserialized["silence_end"],
        "donor_end": deserialized["donor_end"],
        "client_details": deserialized["client_details"],
        "login_time": deserialized["login_time"],
        "last_recv_time": deserialized["last_recv_time"],
        "is_bot_client": deserialized["is_bot_client"],
        "is_tourney_client": deserialized["is_tourney_client"],
        "api_key": deserialized["api_key"],
        "away_msg": deserialized["away_msg"],
        "in_lobby": deserialized["in_lobby"],
        "status": {
            "action": Action(deserialized["status"]["action"]),
            "info_text": deserialized["status"]["info_text"],
            "map_md5": deserialized["status"]["map_md5"],
            "mods": Mods(deserialized["status"]["mods"]),
            "mode": GameMode(deserialized["status"]["mode"]),
            "map_id": deserialized["status"]["map_id"],
        },
        "friend_ids": set(deserialized["friend_ids"]),
        "blocked_ids": set(deserialized["blocked_ids"]),
        "channel_ids": deserialized["channel_ids"],
        "spectator_session_ids": deserialized["spectator_session_ids"],
        "spectating_session_id": deserialized["spectating_session_id"],
        "match_id": deserialized["match_id"],
        "pres_filter": PresenceFilter(deserialized["pres_filter"]),
        "recent_score_ids": {
            GameMode(mode): score_id
            for mode, score_id in deserialized["recent_scores"].items()
        },
        "last_np": deserialized["last_np"],
    }
    return osu_session


def make_redis_key(session_id: str) -> str:
    return f"bancho:osu_sessions:{session_id}"


async def create(
    user_id: int,
    name: str,
    priv: Privileges,
    pw_bcrypt: bytes | None,
    session_id: str,
    clan_id: int | None = None,
    clan_priv: ClanPrivileges | None = None,
    geoloc: app.state.services.Geolocation | None = None,
    utc_offset: int = 0,
    pm_private: bool = False,
    silence_end: int = 0,
    donor_end: int = 0,
    client_details: ClientDetails | None = None,
    login_time: float = 0.0,
    last_recv_time: float = 0.0,
    is_bot_client: bool = False,
    is_tourney_client: bool = False,
    api_key: str | None = None,
    away_msg: str | None = None,
    in_lobby: bool = False,
    status: Status | None = None,
    friend_ids: set[int] | None = None,
    blocked_ids: set[int] | None = None,
    channel_ids: set[int] | None = None,
    spectator_session_ids: set[str] | None = None,
    spectating_session_id: str | None = None,
    match_id: int | None = None,
    pres_filter: PresenceFilter = PresenceFilter.All,
    recent_score_ids: dict[GameMode, int | None] | None = None,
    last_np: LastNp | None = None,
) -> OsuSession:
    """Create a new osu! session in redis."""
    if geoloc is None:
        geoloc = {
            "latitude": 0.0,
            "longitude": 0.0,
            "country": {
                "acronym": "XX",
                "numeric": 0,
            },
        }
    if status is None:
        status = {
            "action": Action.Idle,
            "info_text": "",
            "map_md5": "",
            "mods": Mods.NOMOD,
            "mode": GameMode.VANILLA_OSU,
            "map_id": 0,
        }
    if friend_ids is None:
        friend_ids = set()
    if blocked_ids is None:
        blocked_ids = set()
    if channel_ids is None:
        channel_ids = set()
    if spectator_session_ids is None:
        spectator_session_ids = set()
    if recent_score_ids is None:
        recent_score_ids = {mode: None for mode in GameMode}

    osu_session: OsuSession = {
        "user_id": user_id,
        "name": name,
        "priv": priv,
        "pw_bcrypt": pw_bcrypt,
        "session_id": session_id,
        "clan_id": clan_id,
        "clan_priv": clan_priv,
        "geoloc": geoloc,
        "utc_offset": utc_offset,
        "pm_private": pm_private,
        "silence_end": silence_end,
        "donor_end": donor_end,
        "client_details": client_details,
        "login_time": login_time,
        "last_recv_time": last_recv_time,
        "is_bot_client": is_bot_client,
        "is_tourney_client": is_tourney_client,
        "api_key": api_key,
        "away_msg": away_msg,
        "in_lobby": in_lobby,
        "status": status,
        "friend_ids": friend_ids,
        "blocked_ids": blocked_ids,
        "channel_ids": channel_ids,
        "spectator_session_ids": spectator_session_ids,
        "spectating_session_id": spectating_session_id,
        "match_id": match_id,
        "pres_filter": pres_filter,
        "recent_score_ids": recent_score_ids,
        "last_np": last_np,
    }
    await app.state.services.redis.set(
        name=make_redis_key(session_id),
        value=serialize(osu_session),
        # TODO: set TTL on all write ops?
    )
    return osu_session


async def fetch_main_user_session(
    user_id: int | None = None,
    username: str | None = None,
) -> OsuSession | None:
    assert user_id or username, "user_id or username must be provided"

    cursor = None

    while cursor != 0:
        cursor, keys = await app.state.services.redis.scan(
            cursor=cursor or 0,
            match="bancho:osu_sessions:*",
        )
        serialized_osu_sessions = await app.state.services.redis.mget(keys)
        for serialized in serialized_osu_sessions:
            osu_session = deserialize(serialized)

            if user_id is not None:
                if osu_session["user_id"] != user_id:
                    continue

            if username is not None:
                if osu_session["name"] != username:
                    continue

            if osu_session["client_details"] is None:
                continue

            if osu_session["client_details"].osu_version.stream is OsuStream.TOURNEY:
                continue

            return osu_session

    return None


async def fetch_all(
    user_id: int | None = None,
    username: str | None = None,
) -> list[OsuSession]:
    cursor = None
    osu_sessions = []

    while cursor != 0:
        cursor, keys = await app.state.services.redis.scan(
            cursor=cursor or 0,
            match="bancho:osu_sessions:*",
        )
        serialized_osu_sessions = await app.state.services.redis.mget(keys)
        for serialized in serialized_osu_sessions:
            osu_session = deserialize(serialized)

            if user_id is not None and osu_session["user_id"] != user_id:
                continue

            if username is not None and osu_session["name"] != username:
                continue

            osu_sessions.append(osu_session)

    return osu_sessions


async def fetch_one(session_id: str) -> OsuSession | None:
    raw_osu_session = await app.state.services.redis.get(
        name=make_redis_key(session_id),
    )

    if raw_osu_session is None:
        return None

    return deserialize(raw_osu_session)


async def partial_update(
    session_id: str,
    name: str | _UnsetSentinel = UNSET,
    priv: Privileges | _UnsetSentinel = UNSET,
    pw_bcrypt: bytes | None | _UnsetSentinel = UNSET,
    clan_id: int | None | _UnsetSentinel = UNSET,
    clan_priv: ClanPrivileges | None | _UnsetSentinel = UNSET,
    geoloc: app.state.services.Geolocation | _UnsetSentinel = UNSET,
    pm_private: bool | _UnsetSentinel = UNSET,
    silence_end: int | _UnsetSentinel = UNSET,
    donor_end: int | _UnsetSentinel = UNSET,
    last_recv_time: float | _UnsetSentinel = UNSET,
    api_key: str | None | _UnsetSentinel = UNSET,
    away_msg: str | None | _UnsetSentinel = UNSET,
    in_lobby: bool | _UnsetSentinel = UNSET,
    status: Status | _UnsetSentinel = UNSET,
    friend_ids: set[int] | _UnsetSentinel = UNSET,
    blocked_ids: set[int] | _UnsetSentinel = UNSET,
    channel_ids: set[int] | _UnsetSentinel = UNSET,
    spectator_session_ids: set[str] | _UnsetSentinel = UNSET,
    spectating_session_id: str | None | _UnsetSentinel = UNSET,
    match_id: int | None | _UnsetSentinel = UNSET,
    pres_filter: PresenceFilter | _UnsetSentinel = UNSET,
    recent_score_ids: dict[GameMode, int | None] | _UnsetSentinel = UNSET,
    last_np: LastNp | None | _UnsetSentinel = UNSET,
) -> OsuSession | None:
    raw_osu_session = await app.state.services.redis.get(
        name=make_redis_key(session_id),
    )

    if raw_osu_session is None:
        return None

    osu_session = deserialize(raw_osu_session)

    if osu_session is None:
        return None

    update_fields: OsuSessionUpdateFields = {}

    if not isinstance(name, _UnsetSentinel):
        update_fields["name"] = name
    if not isinstance(priv, _UnsetSentinel):
        update_fields["priv"] = priv
    if not isinstance(pw_bcrypt, _UnsetSentinel):
        update_fields["pw_bcrypt"] = pw_bcrypt
    if not isinstance(clan_id, _UnsetSentinel):
        update_fields["clan_id"] = clan_id
    if not isinstance(clan_priv, _UnsetSentinel):
        update_fields["clan_priv"] = clan_priv
    if not isinstance(geoloc, _UnsetSentinel):
        update_fields["geoloc"] = geoloc
    if not isinstance(pm_private, _UnsetSentinel):
        update_fields["pm_private"] = pm_private
    if not isinstance(silence_end, _UnsetSentinel):
        update_fields["silence_end"] = silence_end
    if not isinstance(donor_end, _UnsetSentinel):
        update_fields["donor_end"] = donor_end
    if not isinstance(last_recv_time, _UnsetSentinel):
        update_fields["last_recv_time"] = last_recv_time
    if not isinstance(api_key, _UnsetSentinel):
        update_fields["api_key"] = api_key
    if not isinstance(away_msg, _UnsetSentinel):
        update_fields["away_msg"] = away_msg
    if not isinstance(in_lobby, _UnsetSentinel):
        update_fields["in_lobby"] = in_lobby
    if not isinstance(status, _UnsetSentinel):
        update_fields["status"] = status
    if not isinstance(friend_ids, _UnsetSentinel):
        update_fields["friend_ids"] = friend_ids
    if not isinstance(blocked_ids, _UnsetSentinel):
        update_fields["blocked_ids"] = blocked_ids
    if not isinstance(channel_ids, _UnsetSentinel):
        update_fields["channel_ids"] = channel_ids
    if not isinstance(spectator_session_ids, _UnsetSentinel):
        update_fields["spectator_session_ids"] = spectator_session_ids
    if not isinstance(spectating_session_id, _UnsetSentinel):
        update_fields["spectating_session_id"] = spectating_session_id
    if not isinstance(match_id, _UnsetSentinel):
        update_fields["match_id"] = match_id
    if not isinstance(pres_filter, _UnsetSentinel):
        update_fields["pres_filter"] = pres_filter
    if not isinstance(recent_score_ids, _UnsetSentinel):
        update_fields["recent_score_ids"] = recent_score_ids
    if not isinstance(last_np, _UnsetSentinel):
        update_fields["last_np"] = last_np

    updated_osu_session: OsuSession = {**osu_session, **update_fields}
    await app.state.services.redis.set(
        name=make_redis_key(session_id),
        value=serialize(updated_osu_session),
    )
    return updated_osu_session


async def unicast_osu_data(target_session_id: str, data: bytes) -> None:
    await app.state.services.redis.lpush(  # type: ignore[awaitable]
        name=f"bancho:packet_queues:{target_session_id}",
        *list(data),
    )


async def multicast_osu_data(target_session_ids: set[str], data: bytes) -> None:
    for session_id in target_session_ids:
        await app.state.services.redis.lpush(  # type: ignore[awaitable]
            name=f"bancho:packet_queues:{session_id}",
            *list(data),
        )


async def broadcast_osu_data(data: bytes) -> None:
    osu_sessions = await fetch_all()
    for osu_session in osu_sessions:
        if osu_session["is_bot_client"]:
            continue

        await app.state.services.redis.lpush(  # type: ignore[awaitable]
            name=f"bancho:packet_queues:{osu_session['session_id']}",
            *list(data),
        )


async def read_full_packet_queue(session_id: str) -> bytes:
    packet_queue = await app.state.services.redis.lrange(  # type: ignore[awaitable]
        name=f"bancho:packet_queues:{session_id}",
        start=0,
        end=-1,
    )
    await app.state.services.redis.delete(f"bancho:packet_queues:{session_id}")
    return b"".join(cast(list[bytes], packet_queue))
