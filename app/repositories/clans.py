from __future__ import annotations

from typing import MutableMapping
from typing import Optional

import app.state.services
from app.objects.clan import Clan

cache: MutableMapping[int, Clan] = {}  # {id: clan}

# create

# read


def _fetch_by_id_cache(id: int) -> Optional[Clan]:
    """Fetch a clan from the cache by id."""
    return cache.get(id)


async def _fetch_by_id_database(id: int) -> Optional[Clan]:
    """Fetch a clan from the database by id."""
    row = await app.state.services.database.fetch_one(
        "SELECT * FROM clans WHERE id = :id",
        {"id": id},
    )
    if row is None:
        return None

    # fetch member ids from sql
    member_ids = {
        row["id"]
        for row in await app.state.services.database.fetch_all(
            "SELECT id FROM users WHERE clan_id = :clan_id",
            {"clan_id": id},
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


async def fetch_by_id(id: int) -> Optional[Clan]:
    """Fetch a clan from the cache, or database by id."""
    if clan := _fetch_by_id_cache(id):
        return clan

    if clan := await _fetch_by_id_database(id):
        return clan

    return None


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


# update

# delete
