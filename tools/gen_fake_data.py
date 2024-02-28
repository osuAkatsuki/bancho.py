#!/usr/bin/env python3
"""
Generate & load fake data for performance testing.
"""

from __future__ import annotations

# users
# stats
# maps
# mapsets
# scores
# maybe hwid stuff
import asyncio
import csv
import os
import random
import secrets
import sys

import bcrypt
import databases

sys.path.insert(0, os.path.abspath(os.pardir))
os.chdir(os.path.abspath(os.pardir))
from app.objects.score import SubmissionStatus


def write_stats_table(user_id_range: range):
    with open("mysql-files/stats.csv", "w+") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "id",
                "mode",
                "tscore",
                "rscore",
                "pp",
                "plays",
                "playtime",
                "acc",
                "max_combo",
                "total_hits",
                "replay_views",
                "xh_count",
                "x_count",
                "sh_count",
                "s_count",
                "a_count",
            ],
        )
        for userid in user_id_range:
            for mode in range(8):
                # write stats
                writer.writerow(
                    {
                        k: r"\N" if v is None else v
                        for k, v in {
                            "id": userid,
                            "mode": mode,
                            "tscore": random.randint(0, 1_000_000),
                            "rscore": random.randint(0, 1_000_000),
                            "pp": random.randint(0, 1_000),
                            "plays": random.randint(0, 1_000),
                            "playtime": random.randint(0, 1_000),
                            "acc": random.uniform(0, 100),
                            "max_combo": random.randint(0, 1_000),
                            "total_hits": random.randint(0, 1_000),
                            "replay_views": random.randint(0, 1_000),
                            "xh_count": random.randint(0, 1_000),
                            "x_count": random.randint(0, 1_000),
                            "sh_count": random.randint(0, 1_000),
                            "s_count": random.randint(0, 1_000),
                            "a_count": random.randint(0, 1_000),
                        }.items()
                    },
                )


def write_users_table(user_id_range: range):
    with open("mysql-files/users.csv", "w+") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "id",
                "name",
                "safe_name",
                "email",
                "priv",
                "pw_bcrypt",
                "country",
                "silence_end",
                "donor_end",
                "creation_time",
                "latest_activity",
                "clan_id",
                "clan_priv",
                "preferred_mode",
                "play_style",
                "custom_badge_name",
                "custom_badge_icon",
                "userpage_content",
                "api_key",
            ],
        )
        import hashlib

        pw = bcrypt.hashpw(
            hashlib.md5(b"password").hexdigest().encode(),
            bcrypt.gensalt(),
        ).decode()
        for userid in user_id_range:
            writer.writerow(
                {
                    k: r"\N" if v is None else v
                    for k, v in {
                        "id": userid,
                        "name": f"user{userid}",
                        "safe_name": f"user{userid}",
                        "email": f"{userid}@gmail.com",
                        "priv": 2147483647,  # TODO
                        "pw_bcrypt": pw,
                        "country": "US",
                        "silence_end": 0,
                        "donor_end": 0,
                        "creation_time": 0,
                        "latest_activity": 0,
                        "clan_id": 0,
                        "clan_priv": 0,
                        "preferred_mode": 0,
                        "play_style": 0,
                        "custom_badge_name": None,
                        "custom_badge_icon": None,
                        "userpage_content": None,
                        "api_key": None,
                    }.items()
                },
            )


def write_maps_table():
    # TODO: write maps (vivid)
    ...


def write_scores_table(user_id_range: range):
    with open("mysql-files/scores.csv", "w+") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "id",
                "map_md5",
                "score",
                "pp",
                "acc",
                "max_combo",
                "mods",
                "n300",
                "n100",
                "n50",
                "nmiss",
                "ngeki",
                "nkatu",
                "grade",
                "status",
                "mode",
                "play_time",
                "time_elapsed",
                "client_flags",
                "userid",
                "perfect",
                "online_checksum",
            ],
        )
        # write some scores
        bmap_md5 = "1cf5b2c2edfafd055536d2cefcb89c0e"
        for score_id in range(1, 1_000_000):
            writer.writerow(
                {
                    k: r"\N" if v is None else v
                    for k, v in {
                        "id": score_id,
                        "map_md5": bmap_md5,
                        "score": random.randint(0, 1_000_000),
                        "pp": random.uniform(0, 1_000),
                        "acc": random.uniform(0, 100),
                        "max_combo": random.randint(0, 1_000),
                        "mods": 0,  # TODO
                        "n300": random.randint(0, 1_000),
                        "n100": random.randint(0, 1_000),
                        "n50": random.randint(0, 1_000),
                        "nmiss": random.randint(0, 1_000),
                        "ngeki": random.randint(0, 1_000),
                        "nkatu": random.randint(0, 1_000),
                        "grade": "A",
                        "status": SubmissionStatus.BEST,
                        "mode": 0,
                        "play_time": "2021-01-01 00:00:00",
                        "time_elapsed": random.randint(0, 1_000),
                        "client_flags": random.randint(0, 1_000),
                        "userid": random.choice(user_id_range),
                        "perfect": 0,
                        "online_checksum": secrets.token_hex(16),
                    }.items()
                },
            )


async def main() -> int:

    user_id_range = range(1, 30_000)
    write_users_table(user_id_range)
    write_stats_table(user_id_range)
    write_scores_table(user_id_range)
    # write_maps_table()

    import time

    async with databases.Database("mysql://root:lol123@localhost:3306/bancho") as db:
        for table in ("users", "stats", "maps", "mapsets", "scores"):
            await db.execute(f"TRUNCATE TABLE {table}")

        await db.execute("SELECT 1 FROM users")
        # import os
        # os.system("chmod 777 mysql-files/data.csv")
        # os.system("ls mysql-files")
        st = time.time()
        for table in ("users", "stats", "maps", "mapsets", "scores"):
            try:
                await db.execute(
                    f"""\
                    LOAD DATA INFILE '/var/lib/mysql-files/{table}.csv' INTO TABLE {table}
                    FIELDS TERMINATED BY ',' ENCLOSED BY '"'
                    LINES TERMINATED BY '\r\n';
                    """,
                )
            except Exception as e:
                print("Failed to load data into table", table, e)

        et = time.time()
        print(et - st)

    return 0


asyncio.run(main())
