from __future__ import annotations

from datetime import datetime
from typing import Optional
from typing import TYPE_CHECKING

import databases.core

import app.state
from app.constants.privileges import ClanPrivileges
from app.repositories import clans as clans_repo
from app.repositories import players as players_repo

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

    async def add_member(self, player: Player) -> None:
        """Add a given player to the clan's members."""
        self.member_ids.add(player.id)

        await app.state.services.database.execute(
            "UPDATE users SET clan_id = :clan_id, clan_priv = 1 WHERE id = :user_id",
            {"clan_id": self.id, "user_id": player.id},
        )

        player.clan = self
        player.clan_priv = ClanPrivileges.Member

    async def remove_member(self, player: Player) -> None:
        """Remove a given player from the clan's members."""
        self.member_ids.remove(player.id)

        await players_repo.update(player.id, clan_id=0, clan_priv=0)

        if not self.member_ids:
            # no members left, disband clan.
            await clans_repo.delete(self.id)
            app.state.sessions.clans.remove(self)
        elif player.id == self.owner_id:
            # owner leaving and members left,
            # transfer the ownership.
            # TODO: prefer officers
            self.owner_id = next(iter(self.member_ids))

            await clans_repo.update(self.id, owner=self.owner_id)
            await players_repo.update(self.owner_id, clan_priv=ClanPrivileges.Owner)

        player.clan = None
        player.clan_priv = None

    def __repr__(self) -> str:
        return f"[{self.tag}] {self.name}"
