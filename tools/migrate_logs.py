#!/usr/bin/env python3.9
import asyncio
import re

import databases

# config (touch this)
# mysql://{username}:{passwd}@{host}:{port}/{database}
DB_DSN = "mysql://cmyui:lol123@localhost:3306/gulag_old"
LOG_REGEX = re.compile(
    r"<(.*)\((.*)\)> (?P<action>unrestricted|restricted|unsilenced|silenced|added note) ?(\((.*)\))? ?(\: (?P<note>.*))? ?(?:for (?P<reason>.*))?",
)


async def main() -> int:
    async with databases.Database(DB_DSN) as db:
        async with (
            db.connection() as select_conn,
            db.connection() as update_conn,
        ):
            # add/adjust new columns, keeping them null until we are finished
            print("Creating new columns")

            await update_conn.execute(
                "ALTER TABLE `logs` ADD COLUMN `action` VARCHAR(32) null after `to`",
            )
            await update_conn.execute(
                "ALTER TABLE `logs` MODIFY `msg` VARCHAR(2048) null",
            )  # now used as reason

            # get all logs & change
            print("Getting all old logs")
            for row in await select_conn.fetch_all(f"SELECT * FROM logs"):
                note = row["msg"]

                note_match = LOG_REGEX.match(row["msg"])
                if not note_match:
                    continue

                reason = note_match["reason"]
                note = note_match["note"]

                msg = None
                if reason:
                    msg = reason
                elif note:
                    msg = note

                if note:
                    action = "note"
                else:
                    action = (
                        note_match["action"][:-2]
                        if "silence" not in note_match["reason"]
                        else note_match["action"][:-1]
                    )

                await update_conn.execute(
                    "UPDATE logs SET action = :action, msg = :msg, time = :time WHERE id = :id",
                    {
                        "action": action,
                        "msg": msg,
                        "id": row["id"],
                        "time": row["time"],
                    },
                )

            # change action column to not null
            await update_conn.execute(
                "ALTER TABLE `logs` MODIFY `action` VARCHAR(32) not null",
            )

            print("Finished migrating logs!")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
