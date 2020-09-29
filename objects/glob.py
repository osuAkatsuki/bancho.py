# -*- coding: utf-8 -*-

from typing import Optional
from aiohttp.client import ClientSession
from objects.collections import PlayerList, ChannelList, MatchList
from cmyui import AsyncSQLPoolWrapper, Version, AsyncTCPServer
import config # imported for indirect use

__all__ = ('players', 'channels',
           'matches', 'db', 'cache')

players = PlayerList()
channels = ChannelList()
matches = MatchList()
db: Optional[AsyncSQLPoolWrapper] = None
http: Optional[ClientSession] = None
version: Optional[Version] = None
serv: Optional[AsyncTCPServer] = None

# gulag's main cache.
# the idea here is simple - keep a copy of things either from sql or
# that take a lot of time to produce in memory for quick and easy access.
# ideally, the cache is hidden away in methods so that developers do not
# need to think about it.
cache = {
    # doing bcrypt on a password takes a surplus of 250ms in python
    # (at least on my current [powerful] machine). this is intentional
    # with bcrypt, but to remove some of this performance hit, we only
    # do it on the user's first login.
    # XXX: this may be removed? it's a hard one, the speed benefits
    # are undoubtably good, but it doesn't feel great.. especially
    # with a command like !ev existing, even with almost 100%
    # certainty nothing can be abused, it doesn't feel great. maaybe
    # it could have a setting on whether to enable, but i don't know
    # if that should be the server owners decision, either.
    'bcrypt': {}, # {md5: bcrypt, ...}
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
    'unsubmitted': set(), # {md5, ...}
    # when a score is submitted, the osu! client will submit a
    # performance report of the user's pc along with some technical
    # details about the score. the performance report is submitted
    # in a separate request from the score, so the order we receive
    # them is somewhat arbitrary. we'll use this cache to track the
    # scoreids we've already received, so that when we receive a
    # performance report, we can check sql for the latest score
    # (probably will have some cache of it's own in the future) and
    # check if it's id is in the cache; if so, then we haven't
    # recevied our score yet, so we'll give it some time, this
    # way our report always gets submitted.
    'performance_reports': set() # {scoreid, ...}
}
