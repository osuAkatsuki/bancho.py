from __future__ import annotations

from typing import Any
from typing import Literal
from typing import Mapping
from typing import MutableMapping
from typing import Optional

import app.settings
import app.state.services
from app.objects.beatmap import Beatmap
from app.objects.beatmap import RankedStatus

## in-memory cache

id_cache: Mapping[int, Beatmap] = {}
md5_cache: MutableMapping[str, Beatmap] = {}


def add_to_cache(beatmap: Beatmap) -> None:
    id_cache[beatmap.id] = beatmap
    md5_cache[beatmap.md5] = beatmap


def remove_from_cache(beatmap: Beatmap) -> None:
    del id_cache[beatmap.id]
    del md5_cache[beatmap.md5]


## create
# TODO: beatmap submission

## read

# TODO: is it possible to have `val`s type depend on the key?
async def _fetch(key: Literal["id", "md5"], val: Any) -> Optional[Beatmap]:
    assert key in ("id", "md5")

    row = await app.state.services.database.fetch_one(
        "SELECT md5, id, set_id, "
        "artist, title, version, creator, "
        "filename, last_update, total_length, "
        "max_combo, status, frozen, "
        "plays, passes, mode, bpm, "
        "cs, od, ar, hp, diff "
        "FROM maps "
        f"WHERE {key} = :{key}",
        {key: val},
    )
    if row:
        beatmap = Beatmap(**row)
        add_to_cache(beatmap)
        return beatmap

    # TODO: allow for multiple to be given
    # TODO: per-api key rate limiting
    api_key = str(app.settings.OSU_API_KEY)

    if api_key:
        # https://github.com/ppy/osu-api/wiki#apiget_beatmaps
        async with app.state.services.http_client.get(
            url="https://old.ppy.sh/api/get_beatmaps",
            params={
                "b" if key == "id" else "h": val,
                "k": api_key,
            },
        ) as resp:
            if resp.status != 200:
                return None

            api_data = await resp.json()

        if api_data:  # None or []
            beatmap = Beatmap.from_osuapi_response(api_data[0])
            add_to_cache(beatmap)
            return beatmap

    return None


async def fetch_by_id(id: int) -> Optional[Beatmap]:
    if beatmap := id_cache.get(id):
        return beatmap

    if beatmap := await _fetch("id", id):
        add_to_cache(beatmap)
        return beatmap

    return None


async def fetch_by_md5(md5: str) -> Optional[Beatmap]:
    if beatmap := md5_cache.get(md5):
        return beatmap

    if beatmap := await _fetch("md5", md5):
        add_to_cache(beatmap)
        return beatmap

    return None


async def fetch_rating(beatmap_md5: str) -> Optional[float]:
    row = await app.state.services.database.fetch_one(
        "SELECT AVG(rating) rating FROM ratings WHERE map_md5 = :map_md5",
        {"map_md5": beatmap_md5},
    )

    if row is None:
        return None

    return row["rating"]


## update


async def update_status(beatmap_id: int, new_status: RankedStatus) -> None:
    """Update a beatmap to a new ranked status in the database."""
    await app.state.services.database.execute(
        "UPDATE maps SET status = :status, frozen = 1 WHERE id = :map_id",
        {"status": new_status, "map_id": beatmap_id},
    )

    if beatmap := id_cache.get(beatmap_id):
        beatmap.status = new_status


async def update_playcounts(beatmap_id: int, plays: int, passes: int) -> None:
    """Update a beatmaps playcounts in the database."""
    await app.state.services.database.execute(
        "UPDATE maps SET plays = :plays, passes = :passes WHERE id = :beatmap_id",
        {"plays": plays, "passes": passes, "beatmap_id": beatmap_id},
    )

    if beatmap := id_cache.get(beatmap_id):
        beatmap.plays = plays
        beatmap.passes = passes


## delete
# TODO: beatmap submission
