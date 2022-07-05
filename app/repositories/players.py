from __future__ import annotations

from typing import Any
from typing import Literal
from typing import Mapping
from typing import MutableMapping
from typing import Optional

import app.state.cache
import app.state.services
import app.state.sessions
import app.utils
from app.constants.gamemodes import GameMode
from app.objects.geolocation import Geolocation
from app.objects.geolocation import OSU_COUNTRY_CODES
from app.objects.player import ModeData
from app.objects.player import Player
from app.objects.score import Grade

id_cache: MutableMapping[int, Player] = {}
safe_name_cache: MutableMapping[str, Player] = {}

## create


## read

# TODO: is it possible to have `val`s type depend on the key?
async def _fetch(key: Literal["id", "safe_name"], val: Any) -> Optional[Player]:
    assert key in ("id", "safe_name")

    user_info = await app.state.services.database.fetch_one(
        # TODO: fetch player's utc offset?
        "SELECT id, name, priv, pw_bcrypt, country, "
        "silence_end, clan_id, clan_priv, api_key, donor_end "
        f"FROM users WHERE {key} = :{key}",
        {key: val},
    )
    if user_info is None:
        return None

    player_id = user_info["id"]
    user_info = dict(user_info)  # make mutable copy

    # TODO: store geolocation {ip:geoloc} store as a repository, store ip reference in other objects
    # TODO: fetch their ip from their last login here, update it if they login from different location
    country_acronym = user_info.pop("country")
    geolocation: Geolocation = {
        "latitude": 0.0,
        "longitude": 0.0,
        "country": {
            "acronym": country_acronym,
            "numeric": OSU_COUNTRY_CODES[country_acronym],
        },
    }

    achievements = await fetch_achievement_ids(player_id)
    friends, blocks = await fetch_relationships(player_id)
    stats = await fetch_stats(player_id)
    recent_scores = await fetch_recent_scores(player_id)

    player = Player(
        **user_info,
        stats=stats,
        friends=friends,
        blocks=blocks,
        achievement_ids=achievements,
        geoloc=geolocation,
        recent_scores=recent_scores,
        token=None,
    )

    return player


async def fetch_by_id(id: int) -> Player | None:
    if player := id_cache.get(id):
        return player

    player = await _fetch("id", id)
    if player is None:
        return None

    id_cache[player.id] = player
    safe_name_cache[player.safe_name] = player

    return player


async def fetch_by_name(name: str) -> Player | None:
    safe_name = app.utils.make_safe_name(name)

    if player := safe_name_cache.get(safe_name):
        return player

    player = await _fetch("safe_name", safe_name)
    if player is None:
        return None

    id_cache[player.id] = player
    safe_name_cache[player.safe_name] = player

    return player


async def get_global_rank(player_id: int, mode: GameMode) -> int:
    rank = await app.state.services.redis.zrevrank(
        f"bancho:leaderboard:{mode.value}",
        str(player_id),
    )
    return rank + 1 if rank is not None else 0


async def get_country_rank(player_id: int, mode: GameMode, country: str) -> int:
    rank = await app.state.services.redis.zrevrank(
        f"bancho:leaderboard:{mode.value}:{country}",
        str(player_id),
    )
    return rank + 1 if rank is not None else 0


async def fetch_relationships(player_id: int) -> tuple[set[int], set[int]]:
    """Retrieve `player`'s relationships from sql."""
    player_friends = set()
    player_blocks = set()

    for row in await app.state.services.database.fetch_all(
        "SELECT user2, type FROM relationships WHERE user1 = :user1",
        {"user1": player_id},
    ):
        if row["type"] == "friend":
            player_friends.add(row["user2"])
        else:
            player_blocks.add(row["user2"])

    # always have bot added to friends.
    player_friends.add(1)

    return player_friends, player_blocks


async def fetch_achievement_ids(player_id: int) -> set[int]:
    """Retrieve `player`'s achievements from sql."""
    return {
        row["id"]
        for row in await app.state.services.database.fetch_all(
            "SELECT ua.achid id FROM user_achievements ua "
            "INNER JOIN achievements a ON a.id = ua.achid "
            "WHERE ua.userid = :user_id",
            {"user_id": player_id},
        )
    }


async def fetch_stats(player_id: int) -> Mapping[GameMode, ModeData]:
    """Retrieve `player`'s stats (all modes) from sql."""
    player_stats: Mapping[GameMode, ModeData] = {}

    for row in await app.state.services.database.fetch_all(
        "SELECT mode, tscore, rscore, pp, acc, "
        "plays, playtime, max_combo, total_hits, "
        "xh_count, x_count, sh_count, s_count, a_count "
        "FROM stats "
        "WHERE id = :user_id",
        {"user_id": player_id},
    ):
        row = dict(row)  # make mutable copy
        mode = row.pop("mode")

        # calculate player's rank.
        row["rank"] = await get_global_rank(player_id, GameMode(mode))

        row["grades"] = {
            Grade.XH: row.pop("xh_count"),
            Grade.X: row.pop("x_count"),
            Grade.SH: row.pop("sh_count"),
            Grade.S: row.pop("s_count"),
            Grade.A: row.pop("a_count"),
        }

        player_stats[GameMode(mode)] = ModeData(**row)

    return player_stats


async def fetch_recent_scores(
    player_id: int,
) -> MutableMapping[GameMode, Optional[int]]:
    recent_scores: MutableMapping[GameMode, Optional[int]] = {}

    # TODO: is this doable in a single query?
    for mode in (0, 1, 2, 3, 4, 5, 6, 8):
        row = await app.state.services.database.fetch_one(
            "SELECT id FROM scores WHERE userid = :user_id AND mode = :mode",
            {"user_id": player_id, "mode": mode},
        )
        if row is None:
            recent_scores[GameMode(mode)] = None
        else:
            recent_scores[GameMode(mode)] = row["id"]

    return recent_scores


## update


async def update_name(player_id: int, new_name: str) -> None:
    """Update a player's name to a new value, by id."""
    new_safe_name = app.utils.make_safe_name(new_name)

    await app.state.services.database.execute(
        "UPDATE users SET name = :name, safe_name = :safe_name WHERE id = :user_id",
        {
            "name": new_name,
            "safe_name": new_safe_name,
            "user_id": player_id,
        },
    )

    # if we have a cache entry, update it
    if player := id_cache.get(player_id):
        del safe_name_cache[player.safe_name]
        safe_name_cache[new_safe_name] = player

        player.name = new_name


async def update_privs(player_id: int, new_privileges: int) -> None:
    """Update a player's privileges to a new value, by id."""
    await app.state.services.database.execute(
        "UPDATE users SET priv = :priv WHERE id = :user_id",
        {"priv": new_privileges, "user_id": player_id},
    )

    if player := id_cache.get(player_id):
        player.priv = new_privileges


async def set_donator_end(player_id: int, end: int) -> None:
    """Set the time when a player's donation status ends."""
    await app.state.services.database.execute(
        "UPDATE users SET donor_end = :end WHERE id = :id",
        {"id": player_id, "end": end},
    )


async def silence_until(player_id: int, until: int) -> None:
    """Silence a player until a certain time."""
    await app.state.services.database.execute(
        "UPDATE users SET silence_end = :silence_end WHERE id = :user_id",
        {"silence_end": until, "user_id": player_id},
    )

    if player := id_cache.get(player_id):
        player.silence_end = until


async def unsilence(player_id: int) -> None:
    """Unsilence a player."""
    await app.state.services.database.execute(
        "UPDATE users SET silence_end = 0 WHERE id = :user_id",
        {"user_id": player_id},
    )

    if player := id_cache.get(player_id):
        player.silence_end = 0


async def update_latest_activity(player_id: int) -> None:
    await app.state.services.database.execute(
        "UPDATE users SET latest_activity = UNIX_TIMESTAMP() WHERE id = :user_id",
        {"user_id": player_id},
    )


## delete
