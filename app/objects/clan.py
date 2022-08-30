from __future__ import annotations

from datetime import datetime
from typing import Optional
from typing import TYPE_CHECKING

import databases.core

import app.state
from app.constants.privileges import ClanPrivileges

if TYPE_CHECKING:
    from app.objects.player import Player

__all__ = ("Clan",)


class Clan:
    """A class to represent a single bancho.py clan."""

    def __init__(
        self,
        id: int,
        name: str,
        tag: str,
        created_at: datetime,
        owner_id: int,
        member_ids: Optional[set[int]] = None,
    ) -> None:
        """A class representing one of bancho.py's clans."""
        self.id = id
        self.name = name
        self.tag = tag
        self.created_at = created_at

        self.owner_id = owner_id  # userid

        if member_ids is None:
            member_ids = set()

        self.member_ids = member_ids  # userids

    async def add_member(self, p: Player) -> None:
        """Add a given player to the clan's members."""
        self.member_ids.add(p.id)

        await app.state.services.database.execute(
            "UPDATE users SET clan_id = :clan_id, clan_priv = 1 WHERE id = :user_id",
            {"clan_id": self.id, "user_id": p.id},
        )

        p.clan = self
        p.clan_priv = ClanPrivileges.Member

    async def remove_member(self, p: Player) -> None:
        """Remove a given player from the clan's members."""
        self.member_ids.remove(p.id)

        async with app.state.services.database.connection() as db_conn:
            await db_conn.execute(
                "UPDATE users SET clan_id = 0, clan_priv = 0 WHERE id = :user_id",
                {"user_id": p.id},
            )

            if not self.member_ids:
                # no members left, disband clan.
                await db_conn.execute(
                    "DELETE FROM clans WHERE id = :clan_id",
                    {"clan_id": self.id},
                )
            elif p.id == self.owner_id:
                # owner leaving and members left,
                # transfer the ownership.
                # TODO: prefer officers
                self.owner_id = next(iter(self.member_ids))

                await db_conn.execute(
                    "UPDATE clans SET owner = :user_id WHERE id = :clan_id",
                    {"user_id": self.owner_id, "clan_id": self.id},
                )

                await db_conn.execute(
                    "UPDATE users SET clan_priv = 3 WHERE id = :user_id",
                    {"user_id": self.owner_id},
                )

        p.clan = None
        p.clan_priv = None

    async def members_from_sql(self, db_conn: databases.core.Connection) -> None:
        """Fetch all members from sql."""
        # TODO: in the future, we'll want to add
        # clan 'mods', so fetching rank here may
        # be a good idea to sort people into
        # different roles.
        for row in await db_conn.fetch_all(
            "SELECT id FROM users WHERE clan_id = :clan_id",
            {"clan_id": self.id},
        ):
            self.member_ids.add(row["id"])

    def __repr__(self) -> str:
        return f"[{self.tag}] {self.name}"
