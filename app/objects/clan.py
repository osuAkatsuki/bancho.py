from datetime import datetime
from enum import IntEnum
from enum import unique
from typing import TYPE_CHECKING

import aiomysql
import databases.core

import app.state
from app.utils import escape_enum
from app.utils import pymysql_encode

if TYPE_CHECKING:
    from app.objects.player import Player

__all__ = ("Clan", "ClanPrivileges")


@unique
@pymysql_encode(escape_enum)
class ClanPrivileges(IntEnum):
    """A class to represent a clan members privs."""

    Member = 1
    Officer = 2
    Owner = 3


class Clan:
    """A class to represent a single gulag clan."""

    __slots__ = ("id", "name", "tag", "created_at", "owner", "members")

    def __init__(
        self,
        id: int,
        name: str,
        tag: str,
        created_at: datetime,
        owner: int,
        members: set[int] = set(),
    ) -> None:
        """A class representing one of gulag's clans."""
        self.id = id
        self.name = name
        self.tag = tag
        self.created_at = created_at

        self.owner = owner  # userid
        self.members = members  # userids

    async def add_member(self, p: "Player") -> None:
        """Add a given player to the clan's members."""
        self.members.add(p.id)

        await app.state.services.database.execute(
            "UPDATE users SET clan_id = :clan_id, clan_priv = 1 WHERE id = :user_id",
            {"clan_id": self.id, "user_id": p.id},
        )

        p.clan = self
        p.clan_priv = ClanPrivileges.Member

    async def remove_member(self, p: "Player") -> None:
        """Remove a given player from the clan's members."""
        self.members.remove(p.id)

        async with app.state.services.database.connection() as db_conn:
            await db_conn.execute(
                "UPDATE users SET clan_id = 0, clan_priv = 0 WHERE id = :user_id",
                {"user_id": p.id},
            )

            if not self.members:
                # no members left, disband clan.
                await db_conn.execute(
                    "DELETE FROM clans WHERE id = :clan_id",
                    {"clan_id": self.id},
                )
            elif p.id == self.owner:
                # owner leaving and members left,
                # transfer the ownership.
                # TODO: prefer officers
                self.owner = next(iter(self.members))

                await db_conn.execute(
                    "UPDATE clans SET owner = :user_id WHERE id = :clan_id",
                    {"user_id": self.owner, "clan_id": self.id},
                )

                await db_conn.execute(
                    "UPDATE users SET clan_priv = 3 WHERE id = :user_id",
                    {"user_id": self.owner},
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
            self.members.add(row["id"])

    def __repr__(self) -> str:
        return f"[{self.tag}] {self.name}"
