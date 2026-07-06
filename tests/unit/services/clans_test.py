from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any

import app.services.clans as clans
from app._typing import UNSET
from app._typing import _UnsetSentinel
from app.constants.privileges import ClanPrivileges
from app.constants.privileges import Privileges
from app.repositories.clans import Clan

VISIBLE_PRIV = int(Privileges.UNRESTRICTED | Privileges.VERIFIED)
HIDDEN_PRIV = int(Privileges.UNRESTRICTED)  # unverified
STAFF_PRIV = int(
    Privileges.UNRESTRICTED | Privileges.VERIFIED | Privileges.ADMINISTRATOR,
)


def _user(
    id: int,
    *,
    name: str | None = None,
    priv: int = VISIBLE_PRIV,
    clan_id: int = 0,
    clan_priv: int = 0,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        name=name if name is not None else f"user{id}",
        priv=priv,
        clan_id=clan_id,
        clan_priv=clan_priv,
    )


class _FakeClansRepository:
    def __init__(self, clans_by_id: dict[int, Clan] | None = None) -> None:
        self.clans = clans_by_id or {}

    async def create(self, name: str, tag: str, owner: int) -> Clan:
        clan = Clan(
            id=max(self.clans, default=0) + 1,
            name=name,
            tag=tag,
            owner=owner,
            created_at=datetime(2024, 1, 1),
        )
        self.clans[clan.id] = clan
        return clan

    async def fetch_one(
        self,
        id: int | None = None,
        name: str | None = None,
        tag: str | None = None,
        owner: int | None = None,
    ) -> Clan | None:
        for clan in self.clans.values():
            if id is not None and clan.id != id:
                continue
            if name is not None and clan.name != name:
                continue
            if tag is not None and clan.tag != tag:
                continue
            if owner is not None and clan.owner != owner:
                continue
            return clan
        return None

    async def delete_one(self, id: int) -> Clan | None:
        return self.clans.pop(id, None)

    async def partial_update(
        self,
        id: int,
        owner: int | _UnsetSentinel = UNSET,
    ) -> Clan | None:
        clan = self.clans.get(id)
        if clan is None:
            return None
        if not isinstance(owner, _UnsetSentinel):
            clan = Clan(
                id=clan.id,
                name=clan.name,
                tag=clan.tag,
                owner=owner,
                created_at=clan.created_at,
            )
            self.clans[id] = clan
        return clan


class _FakeUsersRepository:
    def __init__(self, users: list[SimpleNamespace]) -> None:
        self.users = {user.id: user for user in users}

    async def fetch_one(
        self,
        id: int | None = None,
        name: str | None = None,
    ) -> SimpleNamespace | None:
        for user in self.users.values():
            if id is not None and user.id != id:
                continue
            if name is not None and user.name != name:
                continue
            return user
        return None

    async def fetch_many(
        self,
        *,
        clan_id: int,
        include_hidden: bool,
    ) -> list[SimpleNamespace]:
        members = [user for user in self.users.values() if user.clan_id == clan_id]
        if not include_hidden:
            members = [
                member
                for member in members
                if member.priv & VISIBLE_PRIV == VISIBLE_PRIV
            ]
        return members

    async def partial_update(
        self,
        id: int,
        clan_id: int | _UnsetSentinel = UNSET,
        clan_priv: int | _UnsetSentinel = UNSET,
    ) -> SimpleNamespace | None:
        user = self.users.get(id)
        if user is None:
            return None
        if not isinstance(clan_id, _UnsetSentinel):
            user.clan_id = clan_id
        if not isinstance(clan_priv, _UnsetSentinel):
            user.clan_priv = clan_priv
        return user


class _FakeOnlinePlayers:
    def __init__(self, sessions: list[SimpleNamespace] | None = None) -> None:
        self.sessions = {session.id: session for session in (sessions or [])}

    def get(
        self,
        token: str | None = None,
        id: int | None = None,
        name: str | None = None,
    ) -> SimpleNamespace | None:
        return self.sessions.get(id) if id is not None else None


class _FakeTransaction:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    async def __aenter__(self) -> None:
        self.calls.append("transaction_enter")

    async def __aexit__(self, *args: Any) -> None:
        self.calls.append("transaction_exit")


class _FakeDatabase:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def transaction(self) -> _FakeTransaction:
        return _FakeTransaction(self.calls)


def _service(
    *,
    users: list[SimpleNamespace] | None = None,
    clans_by_id: dict[int, Clan] | None = None,
    online: list[SimpleNamespace] | None = None,
) -> tuple[
    clans.ClansService,
    _FakeClansRepository,
    _FakeUsersRepository,
    _FakeDatabase,
]:
    clans_repo = _FakeClansRepository(clans_by_id)
    users_repo = _FakeUsersRepository(users or [])
    database = _FakeDatabase()
    service = clans.ClansService(
        clans=clans_repo,
        users=users_repo,
        online_players=_FakeOnlinePlayers(online),
        database=database,
    )
    return service, clans_repo, users_repo, database


def _clan(id: int = 1, owner: int = 3) -> Clan:
    return Clan(
        id=id,
        name="Sunset Riders",
        tag="SUN",
        owner=owner,
        created_at=datetime(2024, 1, 1),
    )


async def test_create_clan_persists_and_syncs_online_state() -> None:
    session = SimpleNamespace(id=3, clan_id=None, clan_priv=None)
    service, clans_repo, users_repo, database = _service(
        users=[_user(3)],
        online=[session],
    )

    result = await service.create_clan(player_id=3, tag="sun", name="Sunset Riders")

    assert result.code is clans.CreateClanResultCode.CREATED
    assert result.clan is not None
    assert result.clan.tag == "SUN"  # normalized to uppercase
    assert result.clan.owner == 3
    assert users_repo.users[3].clan_id == result.clan.id
    assert users_repo.users[3].clan_priv == ClanPrivileges.Owner
    assert session.clan_id == result.clan.id
    assert session.clan_priv == ClanPrivileges.Owner
    # both writes happen within a single transaction
    assert database.calls == ["transaction_enter", "transaction_exit"]


async def test_create_clan_validates_tag_and_name() -> None:
    service, *_ = _service(users=[_user(3)])

    result = await service.create_clan(player_id=3, tag="TOOLONG", name="Valid Name")
    assert result.code is clans.CreateClanResultCode.INVALID_TAG

    result = await service.create_clan(player_id=3, tag="SUN", name="x")
    assert result.code is clans.CreateClanResultCode.INVALID_NAME


async def test_create_clan_rejects_players_already_in_a_clan() -> None:
    service, *_ = _service(
        users=[_user(3, clan_id=1, clan_priv=int(ClanPrivileges.Member))],
        clans_by_id={1: _clan(owner=4)},
    )

    result = await service.create_clan(player_id=3, tag="NEW", name="New Clan")

    assert result.code is clans.CreateClanResultCode.ALREADY_IN_CLAN
    assert result.current_clan is not None
    assert result.current_clan.id == 1


async def test_create_clan_rejects_taken_tags_and_names() -> None:
    service, *_ = _service(users=[_user(3)], clans_by_id={1: _clan(owner=4)})

    result = await service.create_clan(player_id=3, tag="NEW", name="Sunset Riders")
    assert result.code is clans.CreateClanResultCode.NAME_TAKEN

    result = await service.create_clan(player_id=3, tag="SUN", name="New Clan")
    assert result.code is clans.CreateClanResultCode.TAG_TAKEN


async def test_disband_clan_removes_all_members_even_hidden_ones() -> None:
    owner_session = SimpleNamespace(id=3, clan_id=1, clan_priv=ClanPrivileges.Owner)
    service, clans_repo, users_repo, database = _service(
        users=[
            _user(3, clan_id=1, clan_priv=int(ClanPrivileges.Owner)),
            _user(4, clan_id=1, clan_priv=int(ClanPrivileges.Member)),
            _user(5, clan_id=1, clan_priv=int(ClanPrivileges.Member), priv=HIDDEN_PRIV),
        ],
        clans_by_id={1: _clan()},
        online=[owner_session],
    )

    disbanded = await service.disband_clan(1)

    assert disbanded is not None
    assert clans_repo.clans == {}
    assert all(
        user.clan_id == 0 and user.clan_priv == 0 for user in users_repo.users.values()
    )
    assert owner_session.clan_id is None and owner_session.clan_priv is None
    assert database.calls == ["transaction_enter", "transaction_exit"]


async def test_disband_clan_returns_none_for_missing_clans() -> None:
    service, *_ = _service()
    assert await service.disband_clan(42) is None


async def test_leave_clan_removes_the_member() -> None:
    service, clans_repo, users_repo, database = _service(
        users=[
            _user(3, clan_id=1, clan_priv=int(ClanPrivileges.Owner)),
            _user(4, clan_id=1, clan_priv=int(ClanPrivileges.Member)),
        ],
        clans_by_id={1: _clan()},
    )

    result = await service.leave_clan(4)

    assert result.code is clans.LeaveClanResultCode.LEFT
    assert result.disbanded is False
    assert users_repo.users[4].clan_id == 0
    assert 1 in clans_repo.clans  # clan survives; the owner remains
    assert database.calls == ["transaction_enter", "transaction_exit"]


async def test_leave_clan_rejects_owners_and_clanless_players() -> None:
    service, *_ = _service(
        users=[
            _user(3, clan_id=1, clan_priv=int(ClanPrivileges.Owner)),
            _user(4),
        ],
        clans_by_id={1: _clan()},
    )

    result = await service.leave_clan(3)
    assert result.code is clans.LeaveClanResultCode.OWNER_MUST_TRANSFER

    result = await service.leave_clan(4)
    assert result.code is clans.LeaveClanResultCode.NOT_IN_CLAN


async def test_leave_clan_disbands_when_the_last_member_leaves() -> None:
    # ownerless clans shouldn't occur, but data can drift; the last
    # member walking out takes the clan with them
    service, clans_repo, users_repo, _ = _service(
        users=[_user(4, clan_id=1, clan_priv=int(ClanPrivileges.Member))],
        clans_by_id={1: _clan()},
    )

    result = await service.leave_clan(4)

    assert result.code is clans.LeaveClanResultCode.LEFT
    assert result.disbanded is True
    assert clans_repo.clans == {}


async def test_transfer_clan_ownership_swaps_privileges() -> None:
    owner_session = SimpleNamespace(id=3, clan_id=1, clan_priv=ClanPrivileges.Owner)
    target_session = SimpleNamespace(id=4, clan_id=1, clan_priv=ClanPrivileges.Member)
    service, clans_repo, users_repo, database = _service(
        users=[
            _user(3, clan_id=1, clan_priv=int(ClanPrivileges.Owner)),
            _user(4, clan_id=1, clan_priv=int(ClanPrivileges.Member)),
        ],
        clans_by_id={1: _clan()},
        online=[owner_session, target_session],
    )

    result = await service.transfer_clan_ownership(owner_id=3, target_name="user4")

    assert result.code is clans.TransferClanResultCode.TRANSFERRED
    assert clans_repo.clans[1].owner == 4
    assert users_repo.users[4].clan_priv == ClanPrivileges.Owner
    assert users_repo.users[3].clan_priv == ClanPrivileges.Officer
    assert target_session.clan_priv == ClanPrivileges.Owner
    assert owner_session.clan_priv == ClanPrivileges.Officer
    # all three writes happen within a single transaction
    assert database.calls == ["transaction_enter", "transaction_exit"]


async def test_transfer_clan_ownership_requires_being_the_owner() -> None:
    service, *_ = _service(
        users=[
            _user(3, clan_id=1, clan_priv=int(ClanPrivileges.Member)),
            _user(4),
        ],
        clans_by_id={1: _clan(owner=5)},
    )

    result = await service.transfer_clan_ownership(owner_id=3, target_name="user4")
    assert result.code is clans.TransferClanResultCode.NOT_CLAN_OWNER

    result = await service.transfer_clan_ownership(owner_id=4, target_name="user3")
    assert result.code is clans.TransferClanResultCode.NOT_CLAN_OWNER


async def test_transfer_clan_ownership_rejects_invalid_targets() -> None:
    service, *_ = _service(
        users=[
            _user(3, clan_id=1, clan_priv=int(ClanPrivileges.Owner)),
            _user(4),  # not a clan member
            _user(5, clan_id=1, clan_priv=int(ClanPrivileges.Member), priv=HIDDEN_PRIV),
        ],
        clans_by_id={1: _clan()},
    )

    # players outside the clan are not valid targets
    result = await service.transfer_clan_ownership(owner_id=3, target_name="user4")
    assert result.code is clans.TransferClanResultCode.TARGET_NOT_FOUND

    # hidden members are reported as missing, not revealed
    result = await service.transfer_clan_ownership(owner_id=3, target_name="user5")
    assert result.code is clans.TransferClanResultCode.TARGET_NOT_FOUND

    # transferring to yourself is a no-op
    result = await service.transfer_clan_ownership(owner_id=3, target_name="user3")
    assert result.code is clans.TransferClanResultCode.TARGET_ALREADY_OWNER


async def test_transfer_clan_ownership_staff_owners_can_see_hidden_members() -> None:
    service, clans_repo, *_ = _service(
        users=[
            _user(3, clan_id=1, clan_priv=int(ClanPrivileges.Owner), priv=STAFF_PRIV),
            _user(5, clan_id=1, clan_priv=int(ClanPrivileges.Member), priv=HIDDEN_PRIV),
        ],
        clans_by_id={1: _clan()},
    )

    result = await service.transfer_clan_ownership(owner_id=3, target_name="user5")

    assert result.code is clans.TransferClanResultCode.TRANSFERRED
    assert clans_repo.clans[1].owner == 5
