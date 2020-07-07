# -*- coding: utf-8 -*-

from objects.collections import PlayerList, ChannelList, MatchList
import config

players = PlayerList()
channels = ChannelList()
matches = MatchList()
db = None # too lazy
bcrypt_cache = {}
