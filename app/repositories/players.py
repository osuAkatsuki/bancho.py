from __future__ import annotations

from typing import Any
from typing import Optional

import app.state.cache
import app.state.services
import app.state.sessions
import app.usecases.players
import app.utils
from app.constants.privileges import ClanPrivileges
from app.objects.player import Player

cache = {}


async def _fetch_user_info_sql(key: str, val: Any):  # TODO: type
    # WARNING: do not pass user input into `key`; sql injection
    return await app.state.services.database.fetch_one(
        "SELECT id, name, priv, pw_bcrypt, "
        "silence_end, clan_id, clan_priv, api_key "
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
    player_id: Optional[int] = None,
    player_name: Optional[str] = None,
) -> Player | None:
    arg_key, arg_val = _determine_argument_kv(player_id, player_name)

    # determine correct source
    if player := cache.get(arg_key):
        return player

    user_info = await _fetch_user_info_sql(arg_key, arg_val)

    if user_info is None:
        return None

    user_info = dict(user_info)  # make mutable copy
    player = Player(**user_info, token=None)

    # NOTE: this doesn't set session-specific data like
    # utc_offset, pm_private, login_time, tourney_client, client_details

    async with app.state.services.database.connection() as db_conn:
        await app.usecases.players.achievements_from_sql(player, db_conn)
        await app.usecases.players.stats_from_sql_full(player, db_conn)
        await app.usecases.players.relationships_from_sql(player, db_conn)

        # TODO: fetch player's recent scores from sql

    if user_info["clan_id"] != 0:
        player.clan = app.state.sessions.clans.get(id=user_info["clan_id"])
        player.clan_priv = ClanPrivileges(user_info.pop("clan_priv"))

    cache[player.id] = player
    cache[player.name] = player

    return player
