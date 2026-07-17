from __future__ import annotations

import secrets

import pytest

import app.state.services
from app.constants.privileges import ClanPrivileges
from app.constants.privileges import Privileges
from app.objects.collections import Players
from app.repositories.clans import Clan
from app.repositories.clans import ClansRepository
from app.repositories.users import UsersRepository
from app.services.clans import ClansService
from app.services.clans import CreateClanResultCode
from app.services.clans import LeaveClanResultCode
from app.services.clans import TransferClanResultCode
from tests import factories

VISIBLE_PRIV = int(Privileges.UNRESTRICTED | Privileges.VERIFIED)


class _CreateThenFailClansRepository(ClansRepository):
    async def create(self, name: str, tag: str, owner: int) -> Clan:
        await super().create(name=name, tag=tag, owner=owner)
        raise RuntimeError("fail after clan insert")


def _clans_service(
    *,
    clans: ClansRepository | None = None,
) -> ClansService:
    database = app.state.services.database
    return ClansService(
        clans=clans or ClansRepository(database),
        users=UsersRepository(database),
        online_players=Players(),
        database=database,
    )


async def test_clan_lifecycle_persists_ownership_membership_and_disbanding() -> None:
    owner = await factories.create_user(priv=VISIBLE_PRIV)
    member = await factories.create_user(priv=VISIBLE_PRIV)
    service = _clans_service()

    created = await service.create_clan(
        player_id=owner.id,
        tag=f"T{secrets.token_hex(2)}",
        name=f"Clan {secrets.token_hex(3)}",
    )

    assert created.code is CreateClanResultCode.CREATED
    assert created.clan is not None
    clan = created.clan
    users = UsersRepository(app.state.services.database)
    joined_member = await users.partial_update(
        member.id,
        clan_id=clan.id,
        clan_priv=ClanPrivileges.Member,
    )
    assert joined_member is not None

    transferred = await service.transfer_clan_ownership(
        owner_id=owner.id,
        target_name=member.name,
    )

    assert transferred.code is TransferClanResultCode.TRANSFERRED
    persisted_clan = await ClansRepository(
        app.state.services.database,
    ).fetch_one(id=clan.id)
    persisted_owner = await users.fetch_one(id=owner.id)
    persisted_member = await users.fetch_one(id=member.id)
    assert persisted_clan is not None
    assert persisted_clan.owner == member.id
    assert persisted_owner is not None
    assert persisted_owner.clan_priv == ClanPrivileges.Officer
    assert persisted_member is not None
    assert persisted_member.clan_priv == ClanPrivileges.Owner

    left = await service.leave_clan(owner.id)

    assert left.code is LeaveClanResultCode.LEFT
    assert left.disbanded is False
    persisted_owner = await users.fetch_one(id=owner.id)
    assert persisted_owner is not None
    assert persisted_owner.clan_id == 0
    assert persisted_owner.clan_priv == 0

    disbanded = await service.disband_clan(clan.id)

    assert disbanded is not None
    assert await service.fetch_clan(clan.id) is None
    persisted_member = await users.fetch_one(id=member.id)
    assert persisted_member is not None
    assert persisted_member.clan_id == 0
    assert persisted_member.clan_priv == 0


async def test_create_clan_rolls_back_when_repository_fails_after_insert() -> None:
    owner = await factories.create_user(priv=VISIBLE_PRIV)
    database = app.state.services.database
    service = _clans_service(clans=_CreateThenFailClansRepository(database))
    clan_name = f"Clan {secrets.token_hex(3)}"

    with pytest.raises(RuntimeError, match="fail after clan insert"):
        await service.create_clan(
            player_id=owner.id,
            tag=f"T{secrets.token_hex(2)}",
            name=clan_name,
        )

    assert await ClansRepository(database).fetch_one(name=clan_name) is None
    persisted_owner = await UsersRepository(database).fetch_one(id=owner.id)
    assert persisted_owner is not None
    assert persisted_owner.clan_id == 0
    assert persisted_owner.clan_priv == 0
