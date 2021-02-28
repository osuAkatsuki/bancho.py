# -*- coding: utf-8 -*-

import config # imported for indirect use

if __import__('typing').TYPE_CHECKING:
    from asyncio import Queue
    from aiohttp.client import ClientSession
    from cmyui import AsyncSQLPool
    from cmyui import Version
    from datadog import ThreadStats
    from typing import Optional

    from objects.achievement import Achievement
    from objects.collections import *
    from objects.player import Player
    from objects.score import Score
    from packets import BanchoPacket
    from packets import Packets

__all__ = ('players', 'channels', 'matches',
           'pools', 'clans', 'achievements',
           'bancho_packets', 'db', 'http',
           'version', 'bot', 'cache',
           'sketchy_queue', 'datadog',
           'oppai_built')

# global lists
players: 'PlayerList'
channels: 'ChannelList'
matches: 'MatchList'
clans: 'ClanList'
pools: 'MapPoolList'
achievements: dict[int, list['Achievement']] # per vn gamemode

bancho_packets: dict['Packets', 'BanchoPacket']
db: 'AsyncSQLPool'
http: 'ClientSession'
version: 'Version'
bot: 'Player'
sketchy_queue: 'Queue[Score]'
datadog: 'Optional[ThreadStats]'
oppai_built: bool

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
    'update': { # default timeout is 1h, set on request.
        'cuttingedge': {'check': None, 'path': None, 'timeout': 0},
        'stable40': {'check': None, 'path': None, 'timeout': 0},
        'beta40': {'check': None, 'path': None, 'timeout': 0},
        'stable': {'check': None, 'path': None, 'timeout': 0}
    },
    # cache all beatmap data calculated while online. this way,
    # the most requested maps will inevitably always end up cached.
    'beatmap': {}, # {md5: {timeout, map}, ...}
    # cache all beatmaps which we failed to get from the osuapi,
    # so that we do not have to perform this request multiple times.
    'unsubmitted': set() # {md5, ...}
}
