from __future__ import annotations

import textwrap
from datetime import datetime
from typing import Any
from typing import TypedDict
from typing import cast

import app.state.services

# +--------------+------------------------+------+-----+---------+----------------+
# | Field        | Type                   | Null | Key | Default | Extra          |
# +--------------+------------------------+------+-----+---------+----------------+
# | userid       | int                    | NO   | PRI | NULL    |                |
# | osupath      | char(32)               | NO   | PRI | NULL    |                |
# | adapters     | char(32)               | NO   | PRI | NULL    |                |
# | uninstall_id | char(32)               | NO   | PRI | NULL    |                |
# | disk_serial  | char(32)               | NO   | PRI | NULL    |                |
# | latest_time  | datetime               | NO   |     | NULL    |                |
# | occurrences  | int                    | NO   |     | 0       |                |
# +--------------+------------------------+------+-----+---------+----------------+

READ_PARAMS = textwrap.dedent(
    """\
        userid, osupath, adapters, uninstall_id, disk_serial, latest_time, occurrences
    """,
)


class ClientHash(TypedDict):
    userid: int
    osupath: str
    adapters: str
    uninstall_id: str
    disk_serial: str
    latest_time: datetime
    occurrences: int


class ClientHashWithPlayer(ClientHash):
    name: str
    priv: int


async def create(
    userid: int,
    osupath: str,
    adapters: str,
    uninstall_id: str,
    disk_serial: str,
) -> ClientHash:
    """Create a new client hash entry in the database."""
    query = f"""\
        INSERT INTO client_hashes (userid, osupath, adapters, uninstall_id, disk_serial, latest_time, occurrences)
             VALUES (:userid, :osupath, :adapters, :uninstall_id, :disk_serial, NOW(), 1)
        ON DUPLICATE KEY UPDATE
            latest_time = NOW(),
            occurrences = occurrences + 1
    """
    params: dict[str, Any] = {
        "userid": userid,
        "osupath": osupath,
        "adapters": adapters,
        "uninstall_id": uninstall_id,
        "disk_serial": disk_serial,
    }
    await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM client_hashes
         WHERE userid = :userid
    """
    params = {
        "userid": userid,
    }
    client_hash = await app.state.services.database.fetch_one(query, params)

    assert client_hash is not None
    return cast(ClientHash, dict(client_hash._mapping))


async def fetch_many(
    userid: int,
    running_under_wine: bool,
    adapters: str | None = None,
    uninstall_id: str | None = None,
    disk_serial: str | None = None,
) -> list[ClientHashWithPlayer]:
    """Fetch a list of client hashes from the database."""
    if running_under_wine:
        hw_checks = "h.uninstall_id = :uninstall"
        hw_args = {"uninstall": uninstall_id}
    else:
        hw_checks = "h.adapters = :adapters OR h.uninstall_id = :uninstall OR h.disk_serial = :disk_serial"
        hw_args = {
            "adapters": adapters,
            "uninstall": uninstall_id,
            "disk_serial": disk_serial,
        }

    query = f"""\
        SELECT {READ_PARAMS}, u.name, u.priv
          FROM client_hashes h
          INNER JOIN users u ON h.userid = u.id
            WHERE h.userid = :userid AND ({hw_checks})
    """
    params: dict[str, Any] = {
        "userid": userid,
        **hw_args,
    }

    client_hashes = await app.state.services.database.fetch_all(query, params)
    return cast(
        list[ClientHashWithPlayer],
        [dict(client_hash._mapping) for client_hash in client_hashes],
    )
