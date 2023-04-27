from __future__ import annotations

import csv
import glob
import os.path
import re
import zipfile
from io import BytesIO
from io import StringIO

import app.adapters.email
import app.settings
import app.state
import app.utils
from app.constants import regexes
from app.objects.player import Player

# All user-data related tables and their WHERE query to select the user-related rows

TABLE_USER_ID_COLUMN_NAMES = {
    "clans": "owner",
    "client_hashes": "userid",
    "comments": "userid",
    "favourites": "userid",
    "ingame_logins": "userid",
    # "logs": "`from` OR `to`", # critical data
    "mail": "from_id OR to_id",
    "map_requests": "player_id",
    "ratings": "userid",
    "relationships": "user1",
    "scores": "userid",
    "stats": "id",
    "users": "id",
}


async def generate_table_csv(table: str, user_id: int) -> str:
    """Generates the CSV as a string for the specified table from the table dictionary and user id."""
    user_id_column_name = TABLE_USER_ID_COLUMN_NAMES.get(table)
    if user_id_column_name is None:
        raise KeyError("Table not found.")

    buffer = StringIO()
    writer = csv.writer(buffer, strict=True)

    # fetch the column names for the CSV column row
    columns = await app.state.services.database.fetch_all(
        f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = :table",
        {"table": table},
    )

    writer.writerow(column["COLUMN_NAME"] for column in columns)

    rows = await app.state.services.database.fetch_all(
        f"SELECT * FROM {table} WHERE {user_id_column_name}",
        {"id": user_id},
    )

    for row in rows:
        writer.writerow(row)

    return buffer.getvalue()


async def generate_csvs(user_id: int) -> dict[str, str]:
    """Generates all CSVs for all tables in the table dictionary for the specified user id."""
    return {
        table: await generate_table_csv(table, user_id)
        for table in TABLE_USER_ID_COLUMN_NAMES
    }


async def generate_zip_archive(user_id: int) -> BytesIO:
    """Generates the whole user-data package as a zip archive and returns the BytesIO object."""
    buffer = BytesIO()

    with zipfile.ZipFile(
        file=buffer,
        mode="a",
        compression=zipfile.ZIP_STORED,
        allowZip64=False,
    ) as zip:

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
        with open(app.utils.DATA_PATH / "logs/chat.log") as f:
            for line in f:
                matches = re.findall(
                    regexes.CHATLOG_USER_ID,
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

    buffer.seek(0)
    return buffer


GDPR_HTML_PAGE = """\
<link href="https://fonts.googleapis.com/css?family=Roboto:400,700" rel="stylesheet" type="text/css">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0">
   <tbody>
      <tr>
         <td>
            <h1 style="margin-bottom: 10px; text-align: center; font-family: Roboto, Tahoma, sans-serif; font-size: 65px;">GDPR Request</h1>
         </td>
      </tr>
      <tr>
         <td>
            <h2 style="margin-top: 0px; font-family: Roboto, Tahoma, sans-serif; font-size: 24px; text-align: center;">Hello [NAME]!<br/>Your GDPR data package is ready.<br/>Please view the attachments to download<br/>the uncompressed ZIP archive.</h2>
         </td>
      </tr>
      <tr>
         <td>
            <h3 style="font-family: Roboto, Tahoma, sans-serif; font-size: 18px; color: #95a5a6; text-align: center;">Sent by bancho.py via [DOMAIN]</h3>
         </td>
      </tr>
   </tbody>
</table>
"""


async def send_gdpr_email(player: Player) -> None:
    """Sends an email containing the GDPR data to the specified user."""

    zip = (await generate_zip_archive(player.id)).read()
    attachment = app.adapters.email.get_file_attachment(f"gdpr_{player.id}.zip", zip)

    message = GDPR_HTML_PAGE
    message = message.replace("[NAME]", player.name)
    message = message.replace("[DOMAIN]", app.settings.DOMAIN)

    assert player.email is not None
    app.adapters.email.send_email(
        [player.email],
        "Your GDPR data package is ready!",
        message,
        [attachment],
    )
    player.send_bot("Your GDPR data packge has been sent.")
