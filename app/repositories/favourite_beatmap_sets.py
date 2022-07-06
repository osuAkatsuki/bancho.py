from __future__ import annotations

from app.state import services

## reads


async def exists(player_id: int, map_set_id: int) -> bool:
    return (
        await services.database.fetch_one(
            "SELECT 1 FROM favourites WHERE userid = :user_id AND setid = :set_id",
            {"user_id": player_id, "set_id": map_set_id},
        )
        is not None
    )


async def fetch_set_ids(player_id: int) -> list[int]:
    """Return a list of the user's favourite map set ids."""
    rows = await services.database.fetch_all(
        "SELECT setid FROM favourites WHERE userid = :user_id",
        {"user_id": player_id},
    )

    return [row["setid"] for row in rows]


## writes


async def create(player_id: int, map_set_id: int) -> None:
    await services.database.execute(
        "INSERT INTO favourites VALUES (:user_id, :set_id)",
        {"user_id": player_id, "set_id": map_set_id},
    )
