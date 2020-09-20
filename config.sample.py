# -*- coding: utf-8 -*-

""" server settings """
# The address which the server runs on.
# The server supports both INET4 and UNIX sockets.
# For INET sockets, set to (addr: str, port: int),
# For UNIX sockets, set to the path of the socket.
server_addr = '/tmp/gulag.sock'

# The max amount of concurrent
# connections gulag will hold.
max_conns = 16

# Displays additional information in the
# console, generally for debugging purposes.
debug = False

# Whether the server is running in 'production mode'.
# Having this as false will disable some features that
# aren't used during testing.
server_build = True

# Your MySQL authentication info.
# XXX: we may switch to postgres in the future..
mysql = {
    'db': 'gulag',
    'host': 'localhost',
    'password': 'supersecure',
    'user': 'cmyui'
}

# Your osu!api key. This is required for fetching
# many things, such as beatmap information!
osu_api_key = ''

# The level of gzip compression to use for different tasks.
# When we want to quickly compress something and send it to
# the client immediately, we'd want to focus on optimizing
# both ends (server & client) for overall speed improvement.
# When we are sent data from the client to store long-term and
# serve in the distant future, we want to focus on size &
# decompression speed on the client-side. Remember that higher
# levels will result in diminishing returns; more info below.
# https://www.rootusers.com/gzip-vs-bzip2-vs-xz-performance-comparison/
gzip = {'web': 4, 'disk': 9}

""" osu!direct """
# TODO: add max size to cache on disk.
# perhaps could even make a system to track
# the most commonly downloaded maps to cache?

# Whether you'd like gulag to cache maps on disk.
# gulag will still use an external mirror for new
# downloads, but will keep a cache of osz files
# for ultra speedy downloads.
mirror = True

# The URL of an external mirror
# to use for non-cached maps.
external_mirror = 'https://osu.gatari.pw'

""" customization """
# The menu icon displayed on
# the main menu of osu! ingame.
menu_icon = (
    'https://link.to/my_image.png', # image url
    'https://github.com/cmyui/gulag' # onclick url
)

# Ingame bot command prefix.
command_prefix = '!'

""" caching settings """
# The max duration to
# cache a beatmap for.
# Recommended: ~1 hour.
map_cache_timeout = 3600

# The max duration to cache
# osu-checkupdates requests for.
# Recommended: ~1 hour.
updates_cache_timeout = 3600
