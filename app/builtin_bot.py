from __future__ import annotations

import random
from functools import cache

from app import packets
from app.constants.privileges import Privileges
from app.constants.privileges import get_client_privileges

BOT_USER_ID = 1
BOT_USER_NAME = "Aika"
BOT_PRIVILEGES = (
    Privileges.UNRESTRICTED
    | Privileges.DONATOR
    | Privileges.MODERATOR
    | Privileges.ADMINISTRATOR
    | Privileges.DEVELOPER
)

BOT_USER_STATUSES = (
    (3, "the source code.."),  # editing
    (6, "geohot livestreams.."),  # watching
    (6, "asottile tutorials.."),  # watching
    (6, "over the server.."),  # watching
    (8, "out new features.."),  # testing
    (9, "a pull request.."),  # submitting
)
# lat/long off-screen for in-game world map
BOT_LATITUDE = 1234.0
BOT_LONGITUDE = 4321.0
BOT_UTC_OFFSET = -5  # America/Toronto
BOT_COUNTRY_CODE = 256  # Satellite Provider


@cache
def bot_user_stats() -> bytes:
    """\
    Cached user stats packet for the bot user.

    NOTE: the cache for this is cleared every 5mins by
    `app.bg_loops._update_bot_status`.
    """
    status_id, status_txt = random.choice(BOT_USER_STATUSES)
    return packets.write(
        packets.ServerPackets.USER_STATS,
        (BOT_USER_ID, packets.osuTypes.i32),  # id
        (status_id, packets.osuTypes.u8),  # action
        (status_txt, packets.osuTypes.string),  # info_text
        ("", packets.osuTypes.string),  # map_md5
        (0, packets.osuTypes.i32),  # mods
        (0, packets.osuTypes.u8),  # mode
        (0, packets.osuTypes.i32),  # map_id
        (0, packets.osuTypes.i64),  # rscore
        (0.0, packets.osuTypes.f32),  # acc
        (0, packets.osuTypes.i32),  # plays
        (0, packets.osuTypes.i64),  # tscore
        (0, packets.osuTypes.i32),  # rank
        (0, packets.osuTypes.i16),  # pp
    )


@cache
def bot_user_presence() -> bytes:
    return packets.write(
        packets.ServerPackets.USER_PRESENCE,
        (BOT_USER_ID, packets.osuTypes.i32),
        (BOT_USER_NAME, packets.osuTypes.string),
        (BOT_UTC_OFFSET + 24, packets.osuTypes.u8),
        (BOT_COUNTRY_CODE, packets.osuTypes.u8),
        (get_client_privileges(BOT_PRIVILEGES), packets.osuTypes.u8),
        (BOT_LATITUDE, packets.osuTypes.f32),
        (BOT_LONGITUDE, packets.osuTypes.f32),
        (0, packets.osuTypes.i32),
    )
