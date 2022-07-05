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
    """Retrieve a player from a given key and value."""
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

    stats = await fetch_stats(player_id)
    friends, blocks = await fetch_relationships(player_id)
    achievement_ids = await fetch_achievement_ids(player_id)
    recent_score_ids = await fetch_recent_score_ids(player_id)

    player = Player(
        **user_info,
        stats=stats,
        friends=friends,
        blocks=blocks,
        achievement_ids=achievement_ids,
        geoloc=geolocation,
        recent_score_ids=recent_score_ids,
        token=None,
    )

    return player


async def fetch_by_id(id: int) -> Player | None:
    """Retrieve a player from their id number."""
    if player := id_cache.get(id):
        return player

    player = await _fetch("id", id)
    if player is None:
        return None

    id_cache[player.id] = player
    safe_name_cache[player.safe_name] = player

    return player


async def fetch_by_name(name: str) -> Player | None:
    """Retrieve a player from their username."""
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
    """Retrieve a player's performance-based rank in the world."""
    rank = await app.state.services.redis.zrevrank(
        f"bancho:leaderboard:{mode.value}",
        str(player_id),
    )
    return rank + 1 if rank is not None else 0


async def get_country_rank(player_id: int, mode: GameMode, country: str) -> int:
    """Retrieve a player's performance-based rank in their country."""
    rank = await app.state.services.redis.zrevrank(
        f"bancho:leaderboard:{mode.value}:{country}",
        str(player_id),
    )
    return rank + 1 if rank is not None else 0


async def fetch_relationships(player_id: int) -> tuple[set[int], set[int]]:
    """Retrieve a player's relationships."""
    if player := id_cache.get(player_id):
        return player.friends, player.blocks

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
    """Retrieve a player's achievements."""
    if player := id_cache.get(player_id):
        return player.achievement_ids

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
    """Retrieve a player's stats (for all modes)."""
    if player := id_cache.get(player_id):
        return player.stats

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


async def fetch_recent_score_ids(
    player_id: int,
) -> MutableMapping[GameMode, Optional[int]]:
    """Retrieve a player's recent scores (for all modes)."""
    if player := id_cache.get(player_id):
        return player.recent_score_ids

    recent_score_ids: MutableMapping[GameMode, Optional[int]] = {}

    # TODO: is this doable in a single query?
    for mode in (0, 1, 2, 3, 4, 5, 6, 8):
        row = await app.state.services.database.fetch_one(
            "SELECT id FROM scores WHERE userid = :user_id AND mode = :mode",
            {"user_id": player_id, "mode": mode},
        )
        if row is None:
            recent_score_ids[GameMode(mode)] = None
        else:
            recent_score_ids[GameMode(mode)] = row["id"]

    return recent_score_ids


## update


async def update_name(player_id: int, new_name: str) -> None:
    """Update a player's name to a new value by id."""
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
    """Update a player's privileges to a new value by id."""
    await app.state.services.database.execute(
        "UPDATE users SET priv = :priv WHERE id = :user_id",
        {"priv": new_privileges, "user_id": player_id},
    )

    if player := id_cache.get(player_id):
        player.priv = new_privileges


async def set_donator_end(player_id: int, end: int) -> None:
    """Set the time when a player's donation status ends by id."""
    await app.state.services.database.execute(
        "UPDATE users SET donor_end = :end WHERE id = :id",
        {"id": player_id, "end": end},
    )


async def silence_until(player_id: int, until: int) -> None:
    """Silence a player until a certain time by id."""
    await app.state.services.database.execute(
        "UPDATE users SET silence_end = :silence_end WHERE id = :user_id",
        {"silence_end": until, "user_id": player_id},
    )

    if player := id_cache.get(player_id):
        player.silence_end = until


async def unsilence(player_id: int) -> None:
    """Remove a player's silence by id."""
    await app.state.services.database.execute(
        "UPDATE users SET silence_end = 0 WHERE id = :user_id",
        {"user_id": player_id},
    )

    if player := id_cache.get(player_id):
        player.silence_end = 0


async def update_latest_activity(player_id: int) -> None:
    """Update a player's latest activity date by id."""
    await app.state.services.database.execute(
        "UPDATE users SET latest_activity = UNIX_TIMESTAMP() WHERE id = :user_id",
        {"user_id": player_id},
    )


## delete
