from typing import TYPE_CHECKING

import config  # pylint: disable=unused-import

# this file contains no actualy definitions
if TYPE_CHECKING:
    import asyncio
    import ipaddress
    from datetime import datetime
    from typing import Optional, Type, TypedDict

    import geoip2.database
    from aiohttp.client import ClientSession
    from aioredis import Redis
    from cmyui.mysql import AsyncSQLPool
    from cmyui.version import Version
    from cmyui.web import Server
    from datadog import ThreadStats
    from app.objects.beatmap import Beatmap, BeatmapSet

    # from app.objects.score import Score
    from packets import BasePacket, ClientPackets

    IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address

    class Cache(TypedDict):
        bcrypt: dict[bytes, bytes]

        ip: dict[str, "IPAddress"]

        beatmap: dict[str | int, "Beatmap"]  # bid & md5 keys
        beatmapset: dict[int, "BeatmapSet"]  # bsid keys

        unsubmitted: set[str]
        needs_update: set[str]


__all__ = (
    # current server state
    "players",
    "channels",
    "matches",
    "pools",
    "clans",
    "achievements",
    "version",
    "bot",
    "api_keys",
    "bancho_packets",
    "db",
    "has_internet",
    "shutting_down",
    "boot_time",
    "http_session",
    "datadog",
    "cache",
    "loop",
    "housekeeping_tasks",
    "ongoing_conns",
)

# server object
app: "Server"

version: "Version"

geoloc_db: "Optional[geoip2.database.Reader]"

# currently registered api tokens
api_keys: dict[str, int]  # {api_key: player_id}

# list of registered packets
bancho_packets: dict[str, "dict[ClientPackets, Type[BasePacket]]"]

# active connections
db: "AsyncSQLPool"
redis: "Redis"

has_internet: bool
shutting_down: bool
boot_time: "datetime"
http_session: "Optional[ClientSession]"

datadog: "Optional[ThreadStats]"

# gulag's main cache.
# the idea here is simple - keep a copy of things either from sql or
# that take a lot of time to produce in memory for quick and easy access.
# ideally, the cache is hidden away in methods so that developers do not
# need to think about it.
cache: "Cache" = {
    # algorithms like brypt these are intentionally designed to be
    # slow; we'll cache the results to speed up subsequent logins.
    "bcrypt": {},  # {bcrypt: md5, ...}
    # converting from a stringified ip address to a python ip
    # object is pretty expensive, so we'll cache known ones.
    "ip": {},  # {ip_str: IPAddress, ...}
    # we'll cache results for osu! client update requests since they
    # are relatively frequently and won't change very frequently.
    # cache all beatmap data calculated while online. this way,
    # the most requested maps will inevitably always end up cached.
    "beatmap": {},  # {md5: map, id: map, ...}
    "beatmapset": {},  # {bsid: map_set}
    # cache all beatmaps which are unsubmitted or need an update,
    # since their osu!api requests will fail and thus we'll do the
    # request multiple times which is quite slow & not great.
    "unsubmitted": set(),  # {md5, ...}
    "needs_update": set(),  # {md5, ...}
}

loop: "asyncio.AbstractEventLoop"

housekeeping_tasks: list["asyncio.Task"]
ongoing_conns: list["asyncio.Task"]
