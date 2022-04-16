from __future__ import annotations

from typing import TYPE_CHECKING

import app.state.services
from app.constants.privileges import ClanPrivileges
from app.objects.clan import Clan
from app.objects.player import Player

if TYPE_CHECKING:
    from app.objects.player import Player


async def add_member(clan: Clan, p: Player) -> None:
    """Add a given player to the clan's members."""
    clan.member_ids.add(p.id)

    await app.state.services.database.execute(
        "UPDATE users SET clan_id = :clan_id, clan_priv = 1 WHERE id = :user_id",
        {"clan_id": clan.id, "user_id": p.id},
    )

    p.clan = clan
    p.clan_priv = ClanPrivileges.Member


async def remove_member(clan: Clan, p: Player) -> None:
    """Remove a given player from the clan's members."""
    clan.member_ids.remove(p.id)

    async with app.state.services.database.connection() as db_conn:
        await db_conn.execute(
            "UPDATE users SET clan_id = 0, clan_priv = 0 WHERE id = :user_id",
            {"user_id": p.id},
        )

        if not clan.member_ids:
            # no members left, disband clan.
            await db_conn.execute(
                "DELETE FROM clans WHERE id = :clan_id",
                {"clan_id": clan.id},
            )
        elif p.id == clan.owner_id:
            # owner leaving and members left,
            # transfer the ownership.
            # TODO: prefer officers
            clan.owner_id = next(iter(clan.member_ids))

            await db_conn.execute(
                "UPDATE clans SET owner = :user_id WHERE id = :clan_id",
                {"user_id": clan.owner_id, "clan_id": clan.id},
            )

            await db_conn.execute(
                "UPDATE users SET clan_priv = 3 WHERE id = :user_id",
                {"user_id": clan.owner_id},
            )

    p.clan = None
    p.clan_priv = 0  # TODO:REFACTOR should this be None?
