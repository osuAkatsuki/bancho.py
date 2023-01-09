from __future__ import annotations

import csv
import glob
import os.path
import re
import zipfile
from io import BytesIO
from io import StringIO

import app.settings
import app.state
import app.utils
from app.constants import regexes

# All user-data related tables and their WHERE query to select the user-related rows
table_queries = {
    "clans": "owner = :id",
    "client_hashes": "userid = :id",
    "comments": "userid = :id",
    "favourites": "userid = :id",
    "ingame_logins": "userid = :id",
    #"logs": "`from` = :id OR `to` = :id",
    "mail": "from_id = :id OR to_id = :id",
    "map_requests": "player_id = :id",
    "ratings": "userid = :id",
    "relationships": "user1 = :id OR user2 = :id",
    "scores": "userid = :id",
    "stats": "id = :id",
    "users": "id = :id",
}


async def generate_table_csv(table: str, user_id: int) -> str:
    """Generates the CSV as a string for the specified table from the table dictionary and user id."""
    if not table in table_queries:
        raise KeyError("Table not found.")

    output = StringIO()
    writer = csv.writer(output, strict=True)

    # fetch the column names for the CSV column row
    columns = await app.state.services.database.fetch_all(
        f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = :table",
        {"table": table},
    )

    writer.writerow(column["COLUMN_NAME"] for column in columns)

    rows = await app.state.services.database.fetch_all(
        f"SELECT * FROM {table} WHERE {table_queries[table]}",
        {"id": user_id},
    )

    for row in rows:
        writer.writerow(row)

    return output.getvalue()


async def generate_csvs(user_id: int) -> dict[str, str]:
    """Generates all CSVs for all tables in the table dictionary for the specified user id."""
    csvs = {}

    for table in table_queries.keys():
        csvs[table] = await generate_table_csv(table, user_id)

    return csvs


async def generate_zip_archive(user_id: int) -> BytesIO:
    """Generates the whole user-data package as a zip archive and returns the BytesIO object."""
    output = BytesIO()

    with zipfile.ZipFile(output, "a", zipfile.ZIP_STORED, False) as zip:

        # Add the sql data CSV files to the zip archive
        for table, csv in (await generate_csvs(user_id)).items():
            zip.writestr(f"data/{table}.csv", csv)

        # Add the user avatar to the zip archive
        avatars = glob.glob(str(app.utils.DATA_PATH / "avatars") + f"/{user_id}.*")
        for avatar in avatars:
            with open(avatar, "rb") as file:
                zip.writestr(f"{os.path.split(avatar)[-1]}", file.read())

        # Add the chat logs from .data/logs/chat.log
        chatlog = StringIO()
        file = open(app.utils.DATA_PATH / "logs/chat.log")
        while True:
            line = file.readline()
            if not line:
                break

            matches = re.findall(
                regexes.CHAT_LOG_USER_ID,
                ":".join(line.split(":")[:3]),
            )

            if len(matches) > 0 and matches[0] == str(user_id):
                chatlog.write(line)
            if len(matches) > 1 and matches[1] == str(user_id):
                chatlog.write(line)

        chatlog.seek(0)
        zip.writestr("chat.log", chatlog.getvalue())

        # Get the score ids of all passed scores of the user and add their replays to the archive
        # score_ids = await app.state.services.database.fetch_all(
        #    "SELECT id FROM scores WHERE userid = :userid AND status > 0",
        #    {"userid": user_id}
        # )
        # for id in (x["id"] for x in score_ids):
        #    with open(app.utils.DATA_PATH / f"osr/{id}.osr", "rb") as file:
        #        zip.writestr(f"replays/{id}.osr", file.read())

    output.seek(0)
    return output
