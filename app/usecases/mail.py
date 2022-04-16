from __future__ import annotations

from typing import Any
from typing import Mapping

import app.state.services

# create


async def send(source_id: int, target_id: int, msg: str):
    await app.state.services.database.execute(
        "INSERT INTO `mail` "
        "(`from_id`, `to_id`, `msg`, `time`) "
        "VALUES (:from, :to, :msg, UNIX_TIMESTAMP())",
        {"from": source_id, "to": target_id, "msg": msg},
    )


# read


async def fetch_unread(target_id: int) -> list[Mapping[str, Any]]:
    return await app.state.services.database.fetch_all(
        "SELECT m.`msg`, m.`time`, m.`from_id`, "
        "(SELECT name FROM users WHERE id = m.`from_id`) AS `from`, "
        "(SELECT name FROM users WHERE id = m.`to_id`) AS `to` "
        "FROM `mail` m WHERE m.`to_id` = :to AND m.`read` = 0",
        {"to": target_id},
    )


# update


async def mark_as_read(source_id: int, target_id: int) -> None:
    """Mark any unread mail from this user as read."""
    await app.state.services.database.execute(
        "UPDATE `mail` SET `read` = 1 "
        "WHERE `to_id` = :to AND `from_id` = :from "
        "AND `read` = 0",
        {"to": target_id, "from": source_id},
    )


# delete
