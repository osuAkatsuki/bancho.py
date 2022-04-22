from __future__ import annotations

from datetime import datetime
from typing import MutableMapping
from typing import Optional
from typing import Union

import app.state.services
from app.constants.privileges import ClanPrivileges
from app.objects.clan import Clan
from app.objects.player import Player

ClanID = int
ClanTag = str

KeyTypes = Union[ClanID, ClanTag]

cache: MutableMapping[KeyTypes, Clan] = {}  # {id/tag: clan}

## create


async def create(name: str, tag: str, owner: Player) -> Clan:
    """Create a clan in cache and the database."""
    created_at = datetime.now()

    clan_id = await app.state.services.database.execute(
        "INSERT INTO clans "
        "(name, tag, created_at, owner) "
        "VALUES (:name, :tag, :created_at, :owner_id)",
        {"name": name, "tag": tag, "created_at": created_at, "owner": owner.id},
    )

    clan = Clan(
        id=clan_id,
        name=name,
        tag=tag,
        created_at=created_at,
        owner_id=owner.id,
        member_ids={owner.id},
    )

    # TODO: should this user-specific stuff be another usecase
    owner.clan_id = clan.id
    owner.clan_priv = ClanPrivileges.OWNER

    await app.state.services.database.execute(
        "UPDATE users "
        "SET clan_id = :clan_id, clan_priv = :clan_priv "
        "WHERE id = :user_id",
        {
            "clan_id": owner.clan_id,
            "clan_priv": owner.clan_priv,
            "user_id": owner.id,
        },
    )

    cache[clan.id] = clan
    cache[clan.tag] = clan

    return clan


## read


# low level api
# allow for fetching based on any supported key


def _fetch_by_key_cache(key: KeyTypes) -> Optional[Clan]:
    """Fetch a clan from the cache by any supported key."""
    return cache.get(key)


async def _fetch_by_key_database(key: str, val: KeyTypes) -> Optional[Clan]:
    """Fetch a clan from the database by any supported key."""
    row = await app.state.services.database.fetch_one(
        f"SELECT * FROM clans WHERE {key} = :val",
        {"val": val},
    )
    if row is None:
        return None

    # fetch member ids from sql
    member_ids = {
        row["id"]
        for row in await app.state.services.database.fetch_all(
            "SELECT id FROM users WHERE clan_id = :clan_id",
            {"clan_id": row["id"]},
        )
    }

    return Clan(
        id=row["id"],
        name=row["name"],
        tag=row["tag"],
        created_at=row["created_at"],
        owner_id=row["owner"],  # TODO: fix inconsistency
        member_ids=member_ids,
    )


async def _fetch_by_key(key: str, val: KeyTypes) -> Optional[Clan]:
    """Fetch a clan from the cache, or database by any supported key."""
    if clan := _fetch_by_key_cache(val):
        return clan

    if clan := await _fetch_by_key_database(key, val):
        cache[clan.id] = clan
        return clan

    return None


# high level api


async def fetch_by_id(id: ClanID) -> Optional[Clan]:
    """Fetch a clan from the cache, or database by id."""
    return await _fetch_by_key("id", id)


async def fetch_by_tag(tag: ClanTag) -> Optional[Clan]:
    """Fetch a clan from the cache, or database by tag."""
    return await _fetch_by_key("tag", tag)


async def fetch_all() -> set[Clan]:
    """Fetch all clans from the cache, or database."""
    clan_ids = {
        row["id"]
        for row in await app.state.services.database.fetch_all("SELECT id FROM clans")
    }

    clans = set()
    for id in clan_ids:
        if clan := await fetch_by_id(id):  # should never be false
            clans.add(clan)

    return clans


async def _populate_caches_from_database() -> None:
    """Populate the cache with all values from the database."""
    all_resources = await fetch_all()

    for resource in all_resources:
        cache[resource.id] = resource
        cache[resource.tag] = resource

    return None


# update

# delete


async def delete(clan: Clan) -> None:
    """Delete a clan from the cache and database."""
    await app.state.services.database.execute(
        "DELETE FROM clans WHERE id = :clan_id",
        {"clan_id": clan.id},
    )

    del cache[clan.id]
    del cache[clan.tag]
