#!/usr/bin/env python3.9
"""
tool to merge from gulag 3.5.2 stats to 3.5.3 stats
this tool is destructive, don't run it if you don't know why it exists :)
"""
from __future__ import annotations

import asyncio

import aiomysql
from cmyui.mysql import AsyncSQLPool  # module not in requirements.txt - deprecated

TABLE_COLUMNS = ["tscore", "rscore", "pp", "plays", "playtime", "acc", "max_combo"]


async def main():
    pool = AsyncSQLPool()
    await pool.connect(
        {"db": "gulag_old", "host": "localhost", "password": "lol123", "user": "cmyui"},
    )

    async with pool.pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as main_cursor:
            # rename current table to old_table
            await main_cursor.execute("RENAME TABLE stats TO old_stats")

            # create new stats table
            await main_cursor.execute(
                """
                create table stats
                (
                    id int auto_increment,
                    mode tinyint(1) not null,
                    tscore bigint unsigned default 0 not null,
                    rscore bigint unsigned default 0 not null,
                    pp int unsigned default 0 not null,
                    plays int unsigned default 0 not null,
                    playtime int unsigned default 0 not null,
                    acc float(6,3) default 0.000 not null,
                    max_combo int unsigned default 0 not null,
                    xh_count int unsigned default 0 not null,
                    x_count int unsigned default 0 not null,
                    sh_count int unsigned default 0 not null,
                    s_count int unsigned default 0 not null,
                    a_count int unsigned default 0 not null,
                    primary key (id, mode)
                );
            """,
            )

            # move existing data to new stats table
            await main_cursor.execute("SELECT * FROM old_stats")

            async with conn.cursor(aiomysql.DictCursor) as insert_cursor:
                async for row in main_cursor:
                    # create 7 new rows per user, one for each mode
                    for mode_num, mode_str in enumerate(
                        (
                            "vn_std",
                            "vn_taiko",
                            "vn_catch",
                            "vn_mania",
                            "rx_std",
                            "rx_taiko",
                            "rx_catch",
                            "ap_std",
                        ),
                    ):
                        row_values = [
                            row[f"{column}_{mode_str}"] for column in TABLE_COLUMNS
                        ]

                        await insert_cursor.execute(
                            "INSERT INTO stats "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, "
                            "0, 0, 0, 0, 0)",  # grades (new stuff)
                            [row["id"], mode_num, *row_values],
                        )

            print("success, old table left at old_stats")

    await pool.close()


asyncio.run(main())
