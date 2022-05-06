from __future__ import annotations

from datetime import timedelta
from typing import Any
from typing import Mapping
from typing import MutableMapping
from typing import Optional
from typing import Union

import app.objects.geolocation
import app.state.cache
import app.state.services
import app.state.sessions
import app.utils
from app.constants.gamemodes import GameMode
from app.objects.player import ModeData
from app.objects.player import Player
from app.objects.score import Grade

cache: MutableMapping[Union[int, str], Player] = {}  # {name/id: player}

## create


## read


async def _fetch_user_info_sql(key: str, val: Any):  # TODO: type
    # WARNING: do not pass user input into `key`; sql injection
    return await app.state.services.database.fetch_one(
        "SELECT id, name, priv, pw_bcrypt, country, "
        "silence_end, clan_id, clan_priv, api_key, donor_end "
        f"FROM users WHERE {key} = :{key}",
        {key: val},
    )


def _determine_argument_kv(
    player_id: Optional[int] = None,
    player_name: Optional[str] = None,
) -> tuple[str, Any]:
    if player_id is not None:
        return "id", player_id
    elif player_name is not None:
        return "safe_name", app.utils.make_safe_name(player_name)
    else:
        raise NotImplementedError


async def fetch(
    # support fetching from both args
    id: Optional[int] = None,
    name: Optional[str] = None,
) -> Player | None:
    arg_key, arg_val = _determine_argument_kv(id, name)

    # determine correct source
    if player := cache.get(arg_val):
        return player

    user_info = await _fetch_user_info_sql(arg_key, arg_val)

    if user_info is None:
        return None

    player_id = user_info["id"]

    achievements = await fetch_achievement_ids(player_id)
    friends, blocks = await fetch_relationships(player_id)
    stats = await fetch_stats(player_id)
    recent_scores = await fetch_recent_scores(player_id)

    # TODO: fetch player's utc offset?

    user_info = dict(user_info)  # make mutable copy

    # get geoloc from country acronym
    country_acronym = user_info.pop("country")

    # TODO: store geolocation {ip:geoloc} store as a repository, store ip reference in other objects
    # TODO: fetch their ip from their last login here, update it if they login from different location
    geolocation_data: app.objects.geolocation.Geolocation = {
        "latitude": 0.0,
        "longitude": 0.0,
        "country": {
            "acronym": country_acronym,
            "numeric": app.objects.geolocation.OSU_COUNTRY_CODES[country_acronym],
        },
    }

    player = Player(
        **user_info,
        stats=stats,
        friends=friends,
        blocks=blocks,
        achievement_ids=achievements,
        geoloc=geolocation_data,
        recent_scores=recent_scores,
        token=None,
    )

    # NOTE: this doesn't set session-specific data like
    # utc_offset, pm_private, login_time, tourney_client, client_details

    cache[player.id] = player
    cache[app.utils.make_safe_name(player.name)] = player

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
    await app.state.services.database.execute(
        "UPDATE users SET name = :name, safe_name = :safe_name WHERE id = :user_id",
        {
            "name": new_name,
            "safe_name": app.utils.make_safe_name(new_name),
            "user_id": player_id,
        },
    )

    if player := cache.get(player_id):
        del cache[player.name]
        cache[new_name] = player

        player.name = new_name


async def update_privs(player_id: int, new_privileges: int) -> None:
    """Update a player's privileges to a new value, by id."""
    await app.state.services.database.execute(
        "UPDATE users SET priv = :priv WHERE id = :user_id",
        {"priv": new_privileges, "user_id": player_id},
    )

    if player := cache.get(player_id):
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

    if player := cache.get(player_id):
        player.silence_end = until


async def unsilence(player_id: int) -> None:
    """Unsilence a player."""
    await app.state.services.database.execute(
        "UPDATE users SET silence_end = 0 WHERE id = :user_id",
        {"user_id": player_id},
    )

    if player := cache.get(player_id):
        player.silence_end = 0


async def update_latest_activity(player_id: int) -> None:
    await app.state.services.database.execute(
        "UPDATE users SET latest_activity = UNIX_TIMESTAMP() WHERE id = :user_id",
        {"user_id": player_id},
    )


## delete
