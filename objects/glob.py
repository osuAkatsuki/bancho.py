# -*- coding: utf-8 -*-

from objects.collections import PlayerList, ChannelList, MatchList
import config

players = PlayerList()
channels = ChannelList()
matches = MatchList()
db = None # too lazy
cache = {
    # Doing bcrypt on a password takes a surplus of 250ms in python
    # (at least on my current [powerful] machine). This is intentional
    # with bcrypt, but to remove some of this performance hit, we only
    # do it on the user's first login.
    'bcrypt': {},
    # Update cache is used to cache a result from the official osu!
    # server's /web/check-updates.php page for users on the server.
    'update': {
        'cuttingedge': {'result': None, 'timeout': 0},
        'stable40': {'result': None, 'timeout': 0},
        'beta40': {'result': None, 'timeout': 0},
        'stable': {'result': None, 'timeout': 0}
    }
}
