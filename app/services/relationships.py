from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from app.objects.player import Player
from app.repositories.relationships import RelationshipsRepository
from app.repositories.relationships import RelationshipType
from app.repositories.users import User
from app.repositories.users import UsersRepository


class OnlinePlayers(Protocol):
    def get(
        self,
        token: str | None = None,
        id: int | None = None,
        name: str | None = None,
    ) -> Player | None: ...


class AddFriendResult(StrEnum):
    ADDED = "added"
    ALREADY_FRIENDS = "already_friends"
    TARGET_NOT_FOUND = "target_not_found"
    CANNOT_FRIEND_SELF = "cannot_friend_self"


@dataclass(frozen=True)
class RelationshipsService:
    relationships: RelationshipsRepository
    users: UsersRepository
    online_players: OnlinePlayers

    async def fetch_friends(self, player_id: int) -> list[User]:
        relationships = await self.relationships.fetch_all(
            user1=player_id,
            type=RelationshipType.FRIEND,
        )
        friend_ids = [relationship.user2 for relationship in relationships]
        if not friend_ids:
            return []
        return await self.users.fetch_many(ids=friend_ids)

    async def add_friend(self, player_id: int, target_id: int) -> AddFriendResult:
        if target_id == player_id:
            return AddFriendResult.CANNOT_FRIEND_SELF

        if await self.users.fetch_one(id=target_id) is None:
            return AddFriendResult.TARGET_NOT_FOUND

        existing = await self.relationships.fetch_one(player_id, target_id)
        if existing is not None:
            if existing.type is RelationshipType.FRIEND:
                return AddFriendResult.ALREADY_FRIENDS
            # replace a block with a friendship
            await self.relationships.delete(player_id, target_id)

        await self.relationships.create(
            player_id,
            target_id,
            type=RelationshipType.FRIEND,
        )

        # the game server caches friends in memory for online players
        online_player = self.online_players.get(id=player_id)
        if online_player is not None:
            online_player.friends.add(target_id)

        return AddFriendResult.ADDED

    async def remove_friend(self, player_id: int, target_id: int) -> None:
        existing = await self.relationships.fetch_one(player_id, target_id)
        if existing is None or existing.type is not RelationshipType.FRIEND:
            return

        await self.relationships.delete(player_id, target_id)

        online_player = self.online_players.get(id=player_id)
        if online_player is not None:
            online_player.friends.discard(target_id)
