from __future__ import annotations

import app.state.services


async def fetch_rating(beatmap_md5: str) -> tuple[int, float]:
    """Fetch the beatmap's rating from sql."""
    row = await app.state.services.database.fetch_one(
        "SELECT COUNT(rating) count, IFNULL(SUM(rating), 0.0) total "
        "FROM ratings WHERE map_md5 = :map_md5",
        {"map_md5": beatmap_md5},
    )

    if row is None:
        return (0, 0)

    # NOTE: row['total'] may be a Decimal object
    return (row["count"], float(row["total"]))
