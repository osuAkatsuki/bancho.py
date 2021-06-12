# -*- coding: utf-8 -*-

import config # export

# this file contains no actualy definitions
if __import__('typing').TYPE_CHECKING:
    from asyncio import AbstractEventLoop
    #from asyncio import Queue
    from typing import Optional

    from aiohttp.client import ClientSession
    from cmyui.mysql import AsyncSQLPool
    from cmyui.version import Version
    from cmyui.web import Server
    from datadog import ThreadStats
    import geoip2.database

    from objects.achievement import Achievement
    from objects.collections import Players
    from objects.collections import Channels
    from objects.collections import Matches
    from objects.collections import Clans
    from objects.collections import MapPools
    from objects.player import Player
    #from objects.score import Score
    from packets import BasePacket
    from packets import ClientPackets

__all__ = (
    # current server state
    'players', 'channels', 'matches',
    'pools', 'clans', 'achievements',
    'version', 'bot', 'api_keys',
    'bancho_packets', 'db',
    'has_internet', 'http',
    'datadog', 'cache', 'loop',
    #'sketchy_queue'
)

# server object
app: 'Server'

# current server state
players: 'Players'
channels: 'Channels'
matches: 'Matches'
clans: 'Clans'
pools: 'MapPools'
achievements: list['Achievement']

bot: 'Player'
version: 'Version'

geoloc_db: 'Optional[geoip2.database.Reader]'

# currently registered api tokens
api_keys: dict[str, int] # {api_key: player_id}

# list of registered packets
bancho_packets: dict['ClientPackets', 'BasePacket']

# active connections
db: 'AsyncSQLPool'

has_internet: bool
http: 'Optional[ClientSession]'

datadog: 'Optional[ThreadStats]'

# gulag's main cache.
# the idea here is simple - keep a copy of things either from sql or
# that take a lot of time to produce in memory for quick and easy access.
# ideally, the cache is hidden away in methods so that developers do not
# need to think about it.
cache = {
    # algorithms like brypt these are intentionally designed to be
    # slow; we'll cache the results to speed up subsequent logins.
    'bcrypt': {}, # {bcrypt: md5, ...}
    # we'll cache results for osu! client update requests since they
    # are relatively frequently and won't change very frequently.
    # cache all beatmap data calculated while online. this way,
    # the most requested maps will inevitably always end up cached.
    'beatmap': {}, # {md5: map, id: map, ...}
    'beatmapset': {}, # {bsid: map_set}

    # cache all beatmaps which are unsubmitted or need an update,
    # since their osu!api requests will fail and thus we'll do the
    # request multiple times which is quite slow & not great.
    'unsubmitted': set(), # {md5, ...}
    'needs_update': set() # {md5, ...}
}

loop: 'AbstractEventLoop'

''' (currently unused)
# queue of submitted scores deemed 'sketchy'; to be analyzed.
sketchy_queue: 'Queue[Score]'
'''
