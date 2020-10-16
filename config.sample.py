# -*- coding: utf-8 -*-

""" server settings """
# the domain you'd like gulag to be hosted on.
# XXX: don't include the 'http(s)' prefix, it will be
#      handled automatically situationally by gulag.
domain = 'cmyui.codes' # https://cmyui.codes

# the address which the server runs on.
# the server supports both inet4 and unix sockets.
# for inet sockets, set to (addr: str, port: int),
# for unix sockets, set to the path of the socket.
server_addr = '/tmp/gulag.sock'

# the max amount of concurrent
# connections gulag will hold.
max_conns = 16

# displays additional information in the
# console, generally for debugging purposes.
debug = False

# whether the server is running in 'production mode'.
# having this as false will disable some features that
# aren't used during testing.
server_build = False

# your mysql authentication info.
# XXX: we may switch to postgres in the future..
mysql = {
    'db': 'cmyui',
    'host': 'localhost',
    'password': 'lol123',
    'user': 'cmyui'
}

# your osu!api key. this is required for fetching
# many things, such as beatmap information!
osu_api_key = ''

# the level of gzip compression to use for different tasks.
# when we want to quickly compress something and send it to
# the client immediately, we'd want to focus on optimizing
# both ends (server & client) for overall speed improvement.
# when we are sent data from the client to store long-term and
# serve in the distant future, we want to focus on size &
# decompression speed on the client-side. remember that higher
# levels will result in diminishing returns; more info below.
# https://www.rootusers.com/gzip-vs-bzip2-vs-xz-performance-comparison/
gzip = {'web': 4, 'disk': 9}

""" osu!direct """
# the external mirror url to use.
mirror = 'https://storage.ripple.moe'

""" customization """
# the menu icon displayed on
# the main menu of osu! in-game.
menu_icon = (
    'https://akatsuki.pw/static/logos/logo_ingame.png', # image URL
    'https://akatsuki.pw' # onclick URL
)

# seasonal backgrounds to be displayed
seasonal_bgs = (
    'https://akatsuki.pw/static/flower.png',
)

# in-game bot command prefix.
command_prefix = '!'

# you can hardcode usernames & passwords here to be blocked
# from usage at registration and other vectors to chage them.
# TODO: retrieve the names of the top ~100 (configurable)
# players on bancho, and auto-add them to this set on startup?
disallowed_names = {
    'cookiezi', 'rrtyui',
    'hvick225', 'qsc20010'
}

disallowed_passwords = {
    'password', 'minilamp'
}

""" caching settings """
# the max duration to
# cache a beatmap for.
# recommended: ~1 hour.
map_cache_timeout = 3600

# the max duration to cache
# osu-checkupdates requests for.
# recommended: ~1 hour.
updates_cache_timeout = 3600
