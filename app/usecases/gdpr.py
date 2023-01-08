from __future__ import annotations

import csv
import zipfile
from io import BytesIO
from io import StringIO

import app.state

table_queries = {
    "clans": "owner = :id",
    "client_hashes": "userid = :id",
    "comments": "userid = :id",
    "favourites": "userid = :id",
    "ingame_logins": "userid = :id",
    "logs": "`from` = :id OR `to` = :id",
    "mail": "from_id = :id OR to_id = :id",
    "map_requests": "player_id = :id",
    "ratings": "userid = :id",
    "relationships": "user1 = :id OR user2 = :id",
    "scores": "userid = :id",
    "stats": "id = :id",
    "users": "id = :id",
}


async def generate_table_csv(table: str, user_id: int) -> str:

    if not table in table_queries:
        raise KeyError("Table not found.")

    output = StringIO()
    writer = csv.writer(output, strict=True)

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

    csvs = {}

    for table in table_queries.keys():
        csvs[table] = await generate_table_csv(table, user_id)

    return csvs


async def generate_zip_archive(user_id: int) -> BytesIO:

    output = BytesIO()

    with zipfile.ZipFile(output, "a", zipfile.ZIP_STORED, False) as zip:
        for table, csv in (await generate_csvs(user_id)).items():
            zip.writestr(f"{table}.csv", csv)

    output.seek(0)
    return output
