from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from app.adapters.database import Database
from app.constants.privileges import ClanPrivileges
from app.objects.player import Player
from app.repositories.clans import Clan
from app.repositories.clans import ClansRepository
from app.repositories.users import User
from app.repositories.users import UsersRepository
from app.services.visibility import can_view_player


class OnlinePlayers(Protocol):
    def get(
        self,
        token: str | None = None,
        id: int | None = None,
        name: str | None = None,
    ) -> Player | None: ...


@dataclass(frozen=True)
class ClansListing:
    clans: list[Clan]
    total_clans: int


class CreateClanResultCode(StrEnum):
    CREATED = "created"
    INVALID_TAG = "invalid_tag"
    INVALID_NAME = "invalid_name"
    ALREADY_IN_CLAN = "already_in_clan"
    TAG_TAKEN = "tag_taken"
    NAME_TAKEN = "name_taken"


@dataclass(frozen=True)
class CreateClanResult:
    code: CreateClanResultCode
    clan: Clan | None = None
    # the clan the player is already a member of, for ALREADY_IN_CLAN
    current_clan: Clan | None = None


class LeaveClanResultCode(StrEnum):
    LEFT = "left"
    NOT_IN_CLAN = "not_in_clan"
    OWNER_MUST_TRANSFER = "owner_must_transfer"


@dataclass(frozen=True)
class LeaveClanResult:
    code: LeaveClanResultCode
    clan: Clan | None = None
    # leaving as the last member disbands the clan entirely
    disbanded: bool = False


class TransferClanResultCode(StrEnum):
    TRANSFERRED = "transferred"
    NOT_CLAN_OWNER = "not_clan_owner"
    TARGET_NOT_FOUND = "target_not_found"
    TARGET_ALREADY_OWNER = "target_already_owner"


@dataclass(frozen=True)
class TransferClanResult:
    code: TransferClanResultCode
    clan: Clan | None = None
    target: User | None = None


@dataclass(frozen=True)
class ClansService:
    clans: ClansRepository
    users: UsersRepository
    online_players: OnlinePlayers
    database: Database

    async def fetch_clans(self, *, page: int, page_size: int) -> ClansListing:
        clans = await self.clans.fetch_many(page=page, page_size=page_size)
        total_clans = await self.clans.fetch_count()

        return ClansListing(clans=clans, total_clans=total_clans)

    async def fetch_clan(self, clan_id: int) -> Clan | None:
        return await self.clans.fetch_one(id=clan_id)

    async def fetch_clan_members(self, clan_id: int) -> list[User]:
        # hidden (restricted or unverified) members are not listed
        return await self.users.fetch_many(clan_id=clan_id, include_hidden=False)

    def _sync_online_clan_state(
        self,
        player_id: int,
        *,
        clan_id: int | None,
        clan_priv: ClanPrivileges | None,
    ) -> None:
        """The game server caches clan state on online sessions."""
        online_player = self.online_players.get(id=player_id)
        if online_player is not None:
            online_player.clan_id = clan_id
            online_player.clan_priv = clan_priv

    async def create_clan(
        self,
        *,
        player_id: int,
        tag: str,
        name: str,
    ) -> CreateClanResult:
        tag = tag.upper()
        if not 1 <= len(tag) <= 6:
            return CreateClanResult(code=CreateClanResultCode.INVALID_TAG)
        if not 2 <= len(name) <= 16:
            return CreateClanResult(code=CreateClanResultCode.INVALID_NAME)

        player = await self.users.fetch_one(id=player_id)
        assert player is not None
        if player.clan_id:
            current_clan = await self.clans.fetch_one(id=player.clan_id)
            if current_clan is not None:
                return CreateClanResult(
                    code=CreateClanResultCode.ALREADY_IN_CLAN,
                    current_clan=current_clan,
                )

        if await self.clans.fetch_one(name=name) is not None:
            return CreateClanResult(code=CreateClanResultCode.NAME_TAKEN)
        if await self.clans.fetch_one(tag=tag) is not None:
            return CreateClanResult(code=CreateClanResultCode.TAG_TAKEN)

        async with self.database.transaction():
            clan = await self.clans.create(name=name, tag=tag, owner=player_id)
            await self.users.partial_update(
                player_id,
                clan_id=clan.id,
                clan_priv=ClanPrivileges.Owner,
            )

        self._sync_online_clan_state(
            player_id,
            clan_id=clan.id,
            clan_priv=ClanPrivileges.Owner,
        )
        return CreateClanResult(code=CreateClanResultCode.CREATED, clan=clan)

    async def disband_clan(self, clan_id: int) -> Clan | None:
        clan = await self.clans.fetch_one(id=clan_id)
        if clan is None:
            return None

        members = await self.users.fetch_many(clan_id=clan.id, include_hidden=True)

        async with self.database.transaction():
            await self.clans.delete_one(clan.id)
            for member in members:
                await self.users.partial_update(member.id, clan_id=0, clan_priv=0)

        for member in members:
            self._sync_online_clan_state(member.id, clan_id=None, clan_priv=None)

        return clan

    async def leave_clan(self, player_id: int) -> LeaveClanResult:
        player = await self.users.fetch_one(id=player_id)
        assert player is not None
        if not player.clan_id:
            return LeaveClanResult(code=LeaveClanResultCode.NOT_IN_CLAN)
        if player.clan_priv == ClanPrivileges.Owner:
            return LeaveClanResult(code=LeaveClanResultCode.OWNER_MUST_TRANSFER)

        clan = await self.clans.fetch_one(id=player.clan_id)
        if clan is None:
            return LeaveClanResult(code=LeaveClanResultCode.NOT_IN_CLAN)

        members = await self.users.fetch_many(clan_id=clan.id, include_hidden=True)
        remaining = [member for member in members if member.id != player_id]

        async with self.database.transaction():
            await self.users.partial_update(player_id, clan_id=0, clan_priv=0)
            if not remaining:
                await self.clans.delete_one(clan.id)

        self._sync_online_clan_state(player_id, clan_id=None, clan_priv=None)

        return LeaveClanResult(
            code=LeaveClanResultCode.LEFT,
            clan=clan,
            disbanded=not remaining,
        )

    async def transfer_clan_ownership(
        self,
        *,
        owner_id: int,
        target_name: str,
    ) -> TransferClanResult:
        owner = await self.users.fetch_one(id=owner_id)
        assert owner is not None
        if not owner.clan_id or owner.clan_priv != ClanPrivileges.Owner:
            return TransferClanResult(code=TransferClanResultCode.NOT_CLAN_OWNER)

        clan = await self.clans.fetch_one(id=owner.clan_id)
        if clan is None:
            return TransferClanResult(code=TransferClanResultCode.NOT_CLAN_OWNER)

        target = await self.users.fetch_one(name=target_name)
        # hidden (restricted or unverified) members are reported as
        # missing, matching their visibility everywhere else
        if (
            target is None
            or target.clan_id != clan.id
            or not can_view_player(
                viewer=owner,
                target_id=target.id,
                target_priv=target.priv,
            )
        ):
            return TransferClanResult(code=TransferClanResultCode.TARGET_NOT_FOUND)

        if target.id == owner_id:
            return TransferClanResult(code=TransferClanResultCode.TARGET_ALREADY_OWNER)

        async with self.database.transaction():
            await self.clans.partial_update(clan.id, owner=target.id)
            await self.users.partial_update(
                target.id,
                clan_priv=ClanPrivileges.Owner,
            )
            await self.users.partial_update(
                owner_id,
                clan_priv=ClanPrivileges.Officer,
            )

        for player_id, clan_priv in (
            (target.id, ClanPrivileges.Owner),
            (owner_id, ClanPrivileges.Officer),
        ):
            self._sync_online_clan_state(
                player_id,
                clan_id=clan.id,
                clan_priv=clan_priv,
            )

        return TransferClanResult(
            code=TransferClanResultCode.TRANSFERRED,
            clan=clan,
            target=target,
        )
