#!/usr/bin/env python3.9
import asyncio
import os.path

import databases

# config (touch this)
# mysql://{username}:{passwd}@{host}:{port}/{database}
DB_DSN = "mysql://cmyui:lol123@localhost:3306/gulag_old"

# code (only touch this if u know what ur doing)

SCORES_CREATION_QUERY = """
create table scores (
	id bigint unsigned auto_increment
		primary key,
	map_md5 char(32) not null,
	score int not null,
	pp float(7,3) not null,
	acc float(6,3) not null,
	max_combo int not null,
	mods int not null,
	n300 int not null,
	n100 int not null,
	n50 int not null,
	nmiss int not null,
	ngeki int not null,
	nkatu int not null,
	grade varchar(2) default 'N' not null,
	status tinyint not null,
	mode tinyint not null,
	play_time datetime not null,
	time_elapsed int not null,
	client_flags int not null,
	userid int not null,
	perfect tinyint(1) not null,
	online_checksum char(32) not null
);
"""

SCORES_INSERT_QUERY = """
INSERT INTO scores VALUES (
    NULL,
    :map_md5,
    :score,
    :pp,
    :acc,
    :max_combo,
    :mods,
    :n300,
    :n100,
    :n50,
    :nmiss,
    :ngeki,
    :nkatu,
    :grade,
    :status,
    :mode,
    :play_time,
    :time_elapsed,
    :client_flags,
    :userid,
    :perfect,
    :online_checksum
)"""


async def main() -> int:
    async with databases.Database(DB_DSN, min_size=10, max_size=10) as db:
        async with (
            db.connection() as select_conn,
            db.connection() as update_conn,
        ):
            # create new scores table
            print("Creating new table")
            await update_conn.execute(SCORES_CREATION_QUERY)

            # move all scores (& replays) to their new ids
            for table, mode_addition in (
                ("scores_vn", 0),
                ("scores_rx", 4),
                ("scores_ap", 8),
            ):
                print(f"Moving {table} scores")
                for row in await select_conn.fetch_all(f"SELECT * FROM {table}"):
                    row = dict(row)  # make row mutable

                    old_id = row.pop("id")
                    row["mode"] += mode_addition

                    new_id = await update_conn.execute(SCORES_INSERT_QUERY, row)

                    if os.path.exists(f".data/osr/{old_id}.osr"):
                        print(f"Moving {old_id} replay")
                        os.rename(  # type: ignore
                            f".data/osr/{old_id}.osr",
                            f".data/osr/{new_id}.osr",
                        )

            # move ap!std stats
            await update_conn.execute("UPDATE stats SET mode = 8 WHERE mode = 7")

        if (
            input(
                "Does the new database table seem correct?\n"
                "(Should we drop the old ones?) (y/n)",
            )
            .lower()
            .startswith("y")
        ):
            for table in ("scores_vn", "scores_rx", "scores_ap"):
                print(f"Dropping {table} scores")
                await update_conn.execute(f"DROP TABLE {table}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
