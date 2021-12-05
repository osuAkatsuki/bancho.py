import re
from pathlib import Path
from typing import Optional

import aiomysql
import cmyui
from cmyui.logging import Ansi
from cmyui.logging import log
from sqlalchemy.sql.expression import select

import app.db_models
import app.services
from app.objects import glob

SQL_UPDATES_FILE = Path.cwd() / "migrations/migrations.sql"
VERSION_RGX = re.compile(r"^# v(?P<ver>\d+\.\d+\.\d+)$")


async def _get_current_sql_structure_version() -> Optional[cmyui.Version]:
    """Get the last launched version of the server."""
    row = await app.services.database.fetch_one(
        select(
            [
                app.db_models.startups.c.ver_major,
                app.db_models.startups.c.ver_minor,
                app.db_models.startups.c.ver_micro,
            ],
        )
        .order_by(app.db_models.startups.c.datetime.desc())
        .limit(1),
    )

    if row:
        return cmyui.Version(*map(int, row.values()))


async def run_sql_migrations() -> None:
    """Update the sql structure, if it has changed."""
    if not (current_ver := await _get_current_sql_structure_version()):
        return  # already up to date (server has never run before)

    latest_ver = glob.version

    if latest_ver == current_ver:
        return  # already up to date

    # version changed; there may be sql changes.
    content = SQL_UPDATES_FILE.read_text()

    queries = []
    q_lines = []

    update_ver = None

    for line in content.splitlines():
        if not line:
            continue

        if line.startswith("#"):
            # may be normal comment or new version
            if r_match := VERSION_RGX.fullmatch(line):
                update_ver = cmyui.Version.from_str(r_match["ver"])

            continue
        elif not update_ver:
            continue

        # we only need the updates between the
        # previous and new version of the server.
        if current_ver < update_ver <= latest_ver:
            if line.endswith(";"):
                if q_lines:
                    q_lines.append(line)
                    queries.append(" ".join(q_lines))
                    q_lines = []
                else:
                    queries.append(line)
            else:
                q_lines.append(line)

    if not queries:
        return

    log(
        "Updating mysql structure " f"(v{current_ver!r} -> v{latest_ver!r}).",
        Ansi.LMAGENTA,
    )

    updated = False

    # NOTE: this using a transaction is pretty pointless with mysql since
    # any structural changes to tables will implciticly commit the changes.
    # https://dev.mysql.com/doc/refman/5.7/en/implicit-commit.html
    async with app.services.database.connection() as conn:
        async with conn.cursor() as db_cursor:
            await conn.begin()
            for query in queries:
                try:
                    await db_cursor.execute(query)
                except aiomysql.MySQLError:
                    await conn.rollback()
                    break
            else:
                # all queries ran
                # without problems.
                await conn.commit()
                updated = True

    if not updated:
        log(f"Failed: {query}", Ansi.GRAY)
        log(
            "SQL failed to update - unless you've been "
            "modifying sql and know what caused this, "
            "please please contact cmyui#0425.",
            Ansi.LRED,
        )

        raise KeyboardInterrupt
