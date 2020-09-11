# -*- coding: utf-8 -*-

from typing import Optional
from aiohttp.client import ClientSession
from objects.collections import PlayerList, ChannelList, MatchList
from cmyui import SQLPool, Version
import config # imported for indirect use

__all__ = ('players', 'channels',
           'matches', 'db', 'cache')

players = PlayerList()
channels = ChannelList()
matches = MatchList()
db: Optional[SQLPool] = None
http: Optional[ClientSession] = None
version: Optional[Version] = None

# Gulag's main cache.
# The idea here is simple - keep a copy of things either from SQL or
# that take a lot of time to produce in memory for quick and easy access.
# Ideally, the cache is hidden away in methods so that developers do not
# need to think about it.
cache = {
    # Doing bcrypt on a password takes a surplus of 250ms in python
    # (at least on my current [powerful] machine). This is intentional
    # with bcrypt, but to remove some of this performance hit, we only
    # do it on the user's first login.
    'bcrypt': {},
    # We'll cache results for osu! client update requests since they
    # are relatively frequently and won't change very frequently.
    'update': { # Default timeout is 1h, set on request.
        'cuttingedge': {'check': None, 'path': None, 'timeout': 0},
        'stable40': {'check': None, 'path': None, 'timeout': 0},
        'beta40': {'check': None, 'path': None, 'timeout': 0},
        'stable': {'check': None, 'path': None, 'timeout': 0}
    },
    # Cache all beatmap data calculated while online. This way,
    # the most requested maps will inevitably always end up cached.
    'beatmap': {}, # {md5: {timeout, map}, ...}
    # Cache all beatmaps which we failed to get from the osuapi,
    # so that we do not have to perform this request multiple times.
    'unsubmitted': set()
}
