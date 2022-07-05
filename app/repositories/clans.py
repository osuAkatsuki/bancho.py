from __future__ import annotations

from datetime import datetime
from typing import MutableMapping
from typing import Optional

import app.state.services
from app.constants.privileges import ClanPrivileges
from app.objects.clan import Clan
from app.objects.player import Player


## in-memory cache

id_cache: MutableMapping[int, Clan] = {}
tag_cache: MutableMapping[str, Clan] = {}
name_cache: MutableMapping[str, Clan] = {}


def add_to_cache(clan: Clan) -> None:
    id_cache[clan.id] = clan
    tag_cache[clan.tag] = clan
    name_cache[clan.name] = clan


def remove_from_cache(clan: Clan) -> None:
    del id_cache[clan.id]
    del tag_cache[clan.tag]
    del name_cache[clan.name]


## helpers


async def _member_ids_from_sql(clan_id: int) -> set[int]:
    return {
        row["id"]
        for row in await app.state.services.database.fetch_all(
            "SELECT id FROM users WHERE clan_id = :clan_id",
            {"clan_id": clan_id},
        )
    }


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

    add_to_cache(clan)
    return clan


## read


async def fetch_by_id(id: int) -> Optional[Clan]:
    """Fetch a clan from the cache, or database by id."""
    if clan := id_cache.get(id):
        return clan

    row = await app.state.services.database.fetch_one(
        f"SELECT * FROM clans WHERE id = :id",
        {"id": id},
    )
    if row is None:
        return None

    clan = Clan(
        id=row["id"],
        name=row["name"],
        tag=row["tag"],
        created_at=row["created_at"],
        owner_id=row["owner"],  # TODO: fix inconsistency
        member_ids=await _member_ids_from_sql(row["id"]),
    )

    add_to_cache(clan)
    return clan


async def fetch_by_name(name: str) -> Optional[Clan]:
    """Fetch a clan from the cache, or database by name."""
    if clan := name_cache.get(name):
        return clan

    row = await app.state.services.database.fetch_one(
        f"SELECT * FROM clans WHERE name = :name",
        {"name": name},
    )
    if row is None:
        return None

    clan = Clan(
        id=row["id"],
        name=row["name"],
        tag=row["tag"],
        created_at=row["created_at"],
        owner_id=row["owner"],  # TODO: fix inconsistency
        member_ids=await _member_ids_from_sql(row["id"]),
    )

    add_to_cache(clan)
    return clan


async def fetch_by_tag(tag: str) -> Optional[Clan]:
    """Fetch a clan from the cache, or database by tag."""
    if clan := tag_cache.get(tag):
        return clan

    row = await app.state.services.database.fetch_one(
        f"SELECT * FROM clans WHERE tag = :tag",
        {"tag": tag},
    )
    if row is None:
        return None

    clan = Clan(
        id=row["id"],
        name=row["name"],
        tag=row["tag"],
        created_at=row["created_at"],
        owner_id=row["owner"],  # TODO: fix inconsistency
        member_ids=await _member_ids_from_sql(row["id"]),
    )

    add_to_cache(clan)
    return clan


async def fetch_all() -> set[Clan]:
    """Fetch all clans from the cache, or database."""
    if id_cache:
        return set(id_cache.values())
    else:
        clan_ids = {
            row["id"]
            for row in await app.state.services.database.fetch_all(
                "SELECT id FROM clans",
            )
        }

        clans = set()
        for id in clan_ids:
            if clan := await fetch_by_id(id):  # should never be false
                clans.add(clan)

        return clans


## update

## delete


async def delete(clan: Clan) -> None:
    """Delete a clan from the cache and database."""
    await app.state.services.database.execute(
        "DELETE FROM clans WHERE id = :clan_id",
        {"clan_id": clan.id},
    )

    remove_from_cache(clan)
    return None
