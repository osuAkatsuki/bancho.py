from __future__ import annotations

from typing import TYPE_CHECKING

import app.state.services
from app import repositories
from app.constants.privileges import ClanPrivileges
from app.objects.clan import Clan
from app.objects.player import Player

if TYPE_CHECKING:
    from app.objects.player import Player


# create


async def create(name: str, tag: str, owner: Player) -> Clan:
    """Create a mappool in cache and the database."""
    return await repositories.clans.create(name, tag, owner)


async def add_member(clan: Clan, p: Player) -> None:
    """Add a given player to the clan's members."""
    clan.member_ids.add(p.id)

    await app.state.services.database.execute(
        "UPDATE users SET clan_id = :clan_id, clan_priv = 1 WHERE id = :user_id",
        {"clan_id": clan.id, "user_id": p.id},
    )

    p.clan_id = clan.id
    p.clan_priv = ClanPrivileges.MEMBER


# read

# update

# delete


async def remove_member(clan: Clan, player: Player) -> None:
    """Remove a given player from the clan's members."""
    await app.state.services.database.execute(
        "UPDATE users SET clan_id = 0, clan_priv = 0 WHERE id = :user_id",
        {"user_id": player.id},
    )

    clan.member_ids.remove(player.id)


async def delete(clan: Clan) -> None:
    await repositories.clans.delete(clan)
