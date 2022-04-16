from __future__ import annotations

from typing import MutableMapping
from typing import Optional

import app.state.services
from app.objects.channel import Channel

cache: MutableMapping[str, Channel] = {}

# create

# read


def _fetch_by_name_cache(name: str) -> Optional[Channel]:
    """Fetch a channel from the cache by name."""
    return cache.get(name)


async def _fetch_by_name_database(name: str) -> Optional[Channel]:
    """Fetch a channel from the cache by name."""
    row = await app.state.services.database.fetch_one(
        "SELECT * FROM channels WHERE name = :name",
        {"name": name},
    )
    if row is None:
        return None

    return Channel(
        name=row["name"],
        topic=row["topic"],
        read_priv=row["read_priv"],
        write_priv=row["write_priv"],
        auto_join=row["auto_join"] == 1,
    )


async def fetch_by_name(name: str) -> Optional[Channel]:
    """Fetch a channel from the cache, or database by name."""
    if channel := _fetch_by_name_cache(name):
        return channel

    if channel := await _fetch_by_name_database(name):
        return channel

    return None


async def fetch_all() -> set[Channel]:
    """Fetch all channels from the cache, or database."""
    channel_names = {
        row["name"]
        for row in await app.state.services.database.fetch_all(
            "SELECT name FROM channels",
        )
    }

    channels = set()
    for name in channel_names:
        if channel := await fetch_by_name(name):  # should never be false
            channels.add(channel)

    return channels


# update

# delete
