from __future__ import annotations

from types import SimpleNamespace

import app.services.relationships as relationships
from app.repositories.relationships import Relationship
from app.repositories.relationships import RelationshipType


class _FakeRelationshipsRepository:
    def __init__(self) -> None:
        self.rows: dict[tuple[int, int], str] = {}

    async def create(
        self,
        user1: int,
        user2: int,
        type: RelationshipType,
    ) -> Relationship:
        self.rows[(user1, user2)] = type
        return Relationship(user1=user1, user2=user2, type=type)

    async def fetch_all(
        self,
        user1: int,
        type: RelationshipType | None = None,
    ) -> list[Relationship]:
        return [
            Relationship(user1=u1, user2=u2, type=RelationshipType(row_type))
            for (u1, u2), row_type in self.rows.items()
            if u1 == user1 and (type is None or row_type == type)
        ]

    async def fetch_one(self, user1: int, user2: int) -> Relationship | None:
        row_type = self.rows.get((user1, user2))
        if row_type is None:
            return None
        return Relationship(
            user1=user1,
            user2=user2,
            type=RelationshipType(row_type),
        )

    async def delete(self, user1: int, user2: int) -> None:
        self.rows.pop((user1, user2), None)


class _FakeUsersRepository:
    def __init__(self, user_ids: set[int]) -> None:
        self.user_ids = user_ids

    async def fetch_one(self, id: int | None = None) -> SimpleNamespace | None:
        return SimpleNamespace(id=id) if id in self.user_ids else None

    async def fetch_many(self, ids: list[int]) -> list[SimpleNamespace]:
        return [SimpleNamespace(id=id) for id in ids if id in self.user_ids]


class _FakeOnlinePlayers:
    def __init__(self, online: SimpleNamespace | None = None) -> None:
        self.online = online

    def get(
        self,
        token: str | None = None,
        id: int | None = None,
        name: str | None = None,
    ) -> SimpleNamespace | None:
        if self.online is not None and self.online.id == id:
            return self.online
        return None


def _service(
    *,
    user_ids: set[int],
    relationships_repo: _FakeRelationshipsRepository | None = None,
    online: SimpleNamespace | None = None,
) -> relationships.RelationshipsService:
    return relationships.RelationshipsService(
        relationships=(
            relationships_repo
            if relationships_repo is not None
            else _FakeRelationshipsRepository()
        ),
        users=_FakeUsersRepository(user_ids),
        online_players=_FakeOnlinePlayers(online),
    )


async def test_relationships_service_adds_a_friend() -> None:
    relationships_repo = _FakeRelationshipsRepository()
    service = _service(user_ids={3, 4}, relationships_repo=relationships_repo)

    result = await service.add_friend(3, 4)

    assert result is relationships.AddFriendResult.ADDED
    assert relationships_repo.rows == {(3, 4): "friend"}


async def test_relationships_service_rejects_unknown_targets() -> None:
    relationships_repo = _FakeRelationshipsRepository()
    service = _service(user_ids={3}, relationships_repo=relationships_repo)

    result = await service.add_friend(3, 999)

    assert result is relationships.AddFriendResult.TARGET_NOT_FOUND
    assert relationships_repo.rows == {}


async def test_relationships_service_rejects_self_friending() -> None:
    service = _service(user_ids={3})

    result = await service.add_friend(3, 3)

    assert result is relationships.AddFriendResult.CANNOT_FRIEND_SELF


async def test_relationships_service_does_not_duplicate_friendships() -> None:
    relationships_repo = _FakeRelationshipsRepository()
    relationships_repo.rows[(3, 4)] = "friend"
    service = _service(user_ids={3, 4}, relationships_repo=relationships_repo)

    result = await service.add_friend(3, 4)

    assert result is relationships.AddFriendResult.ALREADY_FRIENDS
    assert relationships_repo.rows == {(3, 4): "friend"}


async def test_relationships_service_replaces_a_block_with_a_friendship() -> None:
    relationships_repo = _FakeRelationshipsRepository()
    relationships_repo.rows[(3, 4)] = "block"
    service = _service(user_ids={3, 4}, relationships_repo=relationships_repo)

    result = await service.add_friend(3, 4)

    assert result is relationships.AddFriendResult.ADDED
    assert relationships_repo.rows == {(3, 4): "friend"}


async def test_relationships_service_updates_the_online_session_cache() -> None:
    online = SimpleNamespace(id=3, friends={1})
    service = _service(user_ids={3, 4}, online=online)

    await service.add_friend(3, 4)
    assert online.friends == {1, 4}

    await service.remove_friend(3, 4)
    assert online.friends == {1}


async def test_relationships_service_removes_a_friend() -> None:
    relationships_repo = _FakeRelationshipsRepository()
    relationships_repo.rows[(3, 4)] = "friend"
    service = _service(user_ids={3, 4}, relationships_repo=relationships_repo)

    await service.remove_friend(3, 4)

    assert relationships_repo.rows == {}


async def test_relationships_service_does_not_remove_blocks_via_unfriend() -> None:
    relationships_repo = _FakeRelationshipsRepository()
    relationships_repo.rows[(3, 4)] = "block"
    service = _service(user_ids={3, 4}, relationships_repo=relationships_repo)

    await service.remove_friend(3, 4)

    assert relationships_repo.rows == {(3, 4): "block"}


async def test_relationships_service_lists_friends() -> None:
    relationships_repo = _FakeRelationshipsRepository()
    relationships_repo.rows[(3, 4)] = "friend"
    relationships_repo.rows[(3, 5)] = "friend"
    relationships_repo.rows[(3, 6)] = "block"
    service = _service(user_ids={3, 4, 5, 6}, relationships_repo=relationships_repo)

    friends = await service.fetch_friends(3)

    assert sorted(friend.id for friend in friends) == [4, 5]
