# -*- coding: utf-8 -*-

from objects.collections import PlayerList, ChannelList, MatchList
from cmyui import SQLPool
import config

__all__ = ('players', 'channels', 'matches', 'db', 'cache')

players = PlayerList()
channels = ChannelList()
matches = MatchList()
db: SQLPool = None # too lazy

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
    # Update cache is used to cache a result from the official osu!
    # server's /web/check-updates.php page for users on the server.
    # This is requested whenever the osu! updater is run while connected,
    # whenever the osu! client returns to the main menu from beatmap
    # selection, and also can be requested from the client's options.
    # Doing a request to peppy's server every time (and in a manner
    # that can easily be spammed ingame) is something I'd rather avoid,
    # so a basic cache for this was nescessary.
    'update': { # Default timeout is 1h, set on request.
        'cuttingedge': {'result': None, 'timeout': 0},
        'stable40': {'result': None, 'timeout': 0},
        'beta40': {'result': None, 'timeout': 0},
        'stable': {'result': None, 'timeout': 0}
    }
    # XXX: I want to do some sort of beatmap cache, I'm just not yet
    #      quite sure on how I want it setup..
}
