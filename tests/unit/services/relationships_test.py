from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.services.relationships as relationships
from app.constants.privileges import Privileges
from app.objects.player import Player
from app.repositories.relationships import Relationship
from app.repositories.relationships import RelationshipType

VISIBLE_PRIV = int(Privileges.UNRESTRICTED | Privileges.VERIFIED)
HIDDEN_PRIV = int(Privileges.UNRESTRICTED)  # unverified


def _user(id: int, priv: int = VISIBLE_PRIV) -> SimpleNamespace:
    return SimpleNamespace(id=id, priv=priv)


def _player(id: int) -> Player:
    return Player(
        id=id,
        name=f"player-{id}",
        priv=Privileges(VISIBLE_PRIV),
        pw_bcrypt=None,
        token=Player.generate_token(),
    )


class _FakeRelationshipsRepository:
    def __init__(self) -> None:
        self.rows: dict[tuple[int, int], str] = {}
        self.operations: list[tuple[str, int, int, RelationshipType | None]] = []
        self.fail_upsert = False

    async def create(
        self,
        user1: int,
        user2: int,
        type: RelationshipType,
    ) -> Relationship:
        self.rows[(user1, user2)] = type
        return Relationship(user1=user1, user2=user2, type=type)

    async def upsert(
        self,
        user1: int,
        user2: int,
        type: RelationshipType,
    ) -> None:
        self.operations.append(("upsert", user1, user2, type))
        if self.fail_upsert:
            raise RuntimeError("relationship upsert failed")
        self.rows[(user1, user2)] = type

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
        self.operations.append(("delete", user1, user2, None))
        self.rows.pop((user1, user2), None)


class _FakeUsersRepository:
    def __init__(self, users: dict[int, SimpleNamespace]) -> None:
        self.users = users

    async def fetch_one(self, id: int | None = None) -> SimpleNamespace | None:
        return self.users.get(id) if id is not None else None

    async def fetch_many(
        self,
        ids: list[int],
        *,
        include_hidden: bool,
    ) -> list[SimpleNamespace]:
        users = [self.users[id] for id in ids if id in self.users]
        if not include_hidden:
            users = [user for user in users if user.priv & VISIBLE_PRIV == VISIBLE_PRIV]
        return users


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
    users: dict[int, SimpleNamespace] | None = None,
    user_ids: set[int] | None = None,
    relationships_repo: _FakeRelationshipsRepository | None = None,
    online: SimpleNamespace | None = None,
) -> relationships.RelationshipsService:
    if users is None:
        users = {id: _user(id) for id in (user_ids or set())}
    return relationships.RelationshipsService(
        relationships=(
            relationships_repo
            if relationships_repo is not None
            else _FakeRelationshipsRepository()
        ),
        users=_FakeUsersRepository(users),
        online_players=_FakeOnlinePlayers(online),
    )


async def test_relationships_service_adds_a_friend() -> None:
    relationships_repo = _FakeRelationshipsRepository()
    service = _service(user_ids={3, 4}, relationships_repo=relationships_repo)

    result = await service.add_friend(_user(3), 4)

    assert result is relationships.AddFriendResult.ADDED
    assert relationships_repo.rows == {(3, 4): "friend"}


async def test_relationships_service_rejects_unknown_targets() -> None:
    relationships_repo = _FakeRelationshipsRepository()
    service = _service(user_ids={3}, relationships_repo=relationships_repo)

    result = await service.add_friend(_user(3), 999)

    assert result is relationships.AddFriendResult.TARGET_NOT_FOUND
    assert relationships_repo.rows == {}


async def test_relationships_service_rejects_hidden_targets() -> None:
    relationships_repo = _FakeRelationshipsRepository()
    service = _service(
        users={3: _user(3), 4: _user(4, priv=HIDDEN_PRIV)},
        relationships_repo=relationships_repo,
    )

    # hidden players are reported as missing, not revealed
    result = await service.add_friend(_user(3), 4)

    assert result is relationships.AddFriendResult.TARGET_NOT_FOUND
    assert relationships_repo.rows == {}


async def test_relationships_service_rejects_self_friending() -> None:
    service = _service(user_ids={3})

    result = await service.add_friend(_user(3), 3)

    assert result is relationships.AddFriendResult.CANNOT_FRIEND_SELF


async def test_relationships_service_does_not_duplicate_friendships() -> None:
    relationships_repo = _FakeRelationshipsRepository()
    relationships_repo.rows[(3, 4)] = "friend"
    service = _service(user_ids={3, 4}, relationships_repo=relationships_repo)

    result = await service.add_friend(_user(3), 4)

    assert result is relationships.AddFriendResult.ALREADY_FRIENDS
    assert relationships_repo.rows == {(3, 4): "friend"}
    assert relationships_repo.operations == []


async def test_relationships_service_replaces_a_block_with_a_friendship() -> None:
    relationships_repo = _FakeRelationshipsRepository()
    relationships_repo.rows[(3, 4)] = "block"
    online = SimpleNamespace(id=3, friends={1}, blocks={4})
    service = _service(
        user_ids={3, 4},
        relationships_repo=relationships_repo,
        online=online,
    )

    result = await service.add_friend(_user(3), 4)

    assert result is relationships.AddFriendResult.ADDED
    assert relationships_repo.rows == {(3, 4): "friend"}
    assert relationships_repo.operations == [
        ("upsert", 3, 4, RelationshipType.FRIEND),
    ]
    assert online.friends == {1, 4}
    assert online.blocks == set()


async def test_relationships_service_preserves_cache_when_friend_upsert_fails() -> None:
    relationships_repo = _FakeRelationshipsRepository()
    relationships_repo.rows[(3, 4)] = "block"
    relationships_repo.fail_upsert = True
    online = SimpleNamespace(id=3, friends={1}, blocks={4})
    service = _service(
        user_ids={3, 4},
        relationships_repo=relationships_repo,
        online=online,
    )

    with pytest.raises(RuntimeError, match="relationship upsert failed"):
        await service.add_friend(_user(3), 4)

    assert relationships_repo.rows == {(3, 4): "block"}
    assert online.friends == {1}
    assert online.blocks == {4}


async def test_relationships_service_updates_the_online_session_cache() -> None:
    online = SimpleNamespace(id=3, friends={1}, blocks=set())
    service = _service(user_ids={3, 4}, online=online)

    await service.add_friend(_user(3), 4)
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


async def test_relationships_service_replaces_a_friend_with_a_block() -> None:
    relationships_repo = _FakeRelationshipsRepository()
    relationships_repo.rows[(3, 4)] = "friend"
    player = _player(3)
    target = _player(4)
    player.friends.add(target.id)
    service = _service(
        user_ids={3, 4},
        relationships_repo=relationships_repo,
    )

    result = await service.add_block(player, target)

    assert result is relationships.AddBlockResult.ADDED
    assert relationships_repo.rows == {(3, 4): "block"}
    assert relationships_repo.operations == [
        ("upsert", 3, 4, RelationshipType.BLOCK),
    ]
    assert player.friends == set()
    assert player.blocks == {4}


async def test_relationships_service_does_not_duplicate_blocks() -> None:
    relationships_repo = _FakeRelationshipsRepository()
    relationships_repo.rows[(3, 4)] = "block"
    player = _player(3)
    target = _player(4)
    player.blocks.add(target.id)
    service = _service(
        user_ids={3, 4},
        relationships_repo=relationships_repo,
    )

    result = await service.add_block(player, target)

    assert result is relationships.AddBlockResult.ALREADY_BLOCKED
    assert relationships_repo.rows == {(3, 4): "block"}
    assert relationships_repo.operations == []
    assert player.blocks == {4}


async def test_relationships_service_preserves_cache_when_block_upsert_fails() -> None:
    relationships_repo = _FakeRelationshipsRepository()
    relationships_repo.rows[(3, 4)] = "friend"
    relationships_repo.fail_upsert = True
    player = _player(3)
    target = _player(4)
    player.friends.add(target.id)
    service = _service(
        user_ids={3, 4},
        relationships_repo=relationships_repo,
    )

    with pytest.raises(RuntimeError, match="relationship upsert failed"):
        await service.add_block(player, target)

    assert relationships_repo.rows == {(3, 4): "friend"}
    assert player.friends == {4}
    assert player.blocks == set()


async def test_relationships_service_removes_a_block() -> None:
    relationships_repo = _FakeRelationshipsRepository()
    relationships_repo.rows[(3, 4)] = "block"
    player = _player(3)
    player.blocks.add(4)
    service = _service(
        user_ids={3, 4},
        relationships_repo=relationships_repo,
    )

    await service.remove_block(player, 4)

    assert relationships_repo.rows == {}
    assert relationships_repo.operations == [("delete", 3, 4, None)]
    assert player.blocks == set()


async def test_relationships_service_does_not_remove_friends_via_unblock() -> None:
    relationships_repo = _FakeRelationshipsRepository()
    relationships_repo.rows[(3, 4)] = "friend"
    player = _player(3)
    player.friends.add(4)
    service = _service(
        user_ids={3, 4},
        relationships_repo=relationships_repo,
    )

    await service.remove_block(player, 4)

    assert relationships_repo.rows == {(3, 4): "friend"}
    assert relationships_repo.operations == []
    assert player.friends == {4}


async def test_relationships_service_hydrates_relationships_and_bot_friend() -> None:
    relationships_repo = _FakeRelationshipsRepository()
    relationships_repo.rows[(3, 4)] = "friend"
    relationships_repo.rows[(3, 5)] = "block"
    player = _player(3)
    service = _service(
        user_ids={3, 4, 5},
        relationships_repo=relationships_repo,
    )

    await service.hydrate_relationships(player, bot_id=1)

    assert player.friends == {1, 4}
    assert player.blocks == {5}


async def test_relationships_service_lists_friends() -> None:
    relationships_repo = _FakeRelationshipsRepository()
    relationships_repo.rows[(3, 4)] = "friend"
    relationships_repo.rows[(3, 5)] = "friend"
    relationships_repo.rows[(3, 6)] = "block"
    service = _service(user_ids={3, 4, 5, 6}, relationships_repo=relationships_repo)

    friends = await service.fetch_friends(_user(3))

    assert sorted(friend.id for friend in friends) == [4, 5]


async def test_relationships_service_omits_hidden_friends() -> None:
    relationships_repo = _FakeRelationshipsRepository()
    relationships_repo.rows[(3, 4)] = "friend"
    relationships_repo.rows[(3, 5)] = "friend"
    service = _service(
        users={3: _user(3), 4: _user(4), 5: _user(5, priv=HIDDEN_PRIV)},
        relationships_repo=relationships_repo,
    )

    # friends who have since become hidden are omitted from the list...
    friends = await service.fetch_friends(_user(3))
    assert sorted(friend.id for friend in friends) == [4]

    # ...unless the viewer is staff
    staff = _user(3, priv=int(Privileges.UNRESTRICTED | Privileges.ADMINISTRATOR))
    friends = await service.fetch_friends(staff)
    assert sorted(friend.id for friend in friends) == [4, 5]
