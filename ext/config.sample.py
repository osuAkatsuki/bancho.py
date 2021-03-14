# -*- coding: utf-8 -*-

""" server settings """
# the domain you'd like gulag to be hosted on.
# XXX: don't include the 'http(s)' prefix, it will be
#      handled automatically situationally by gulag.
domain = 'cmyui.xyz' # cmyui.xyz

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
# NOTE: devs can also toggle ingame w/ !debug.
debug = False

# whether the server is running in 'production mode'.
# having this as false will disable some features that
# aren't used during testing.
production = False

# allow for use of advanced (and potentially dangerous)
# commands. i recommend checking where this config value
# is used throughout the code before enabling it.. :P
advanced = False

# your mysql authentication info.
# NOTE: there is a decent chance we will switch to postgres
# (asyncpg) in the future for better speeds and features in
# the future.. stay tuned.
mysql = {
    'db': 'cmyui',
    'host': 'localhost',
    'password': 'lol123',
    'user': 'cmyui'
}

# your osu!api key, required for
# fetching beatmap information.
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

# the external mirror url to use.
mirror = 'https://storage.ripple.moe'

# the menu icon displayed on
# the main menu of osu! in-game.
menu_icon = (
    'https://akatsuki.pw/static/logos/logo_ingame.png', # image url
    'https://akatsuki.pw' # onclick url
)

# seasonal backgrounds to be displayed ingame.
seasonal_bgs = (
    'https://akatsuki.pw/static/flower.png',
)

# in-game bot command prefix.
command_prefix = '!'

# hardcoded names & passwords users will not be able to use.
# TODO: retrieve the names of the top ~100 (configurable)?
# TODO: add more defaults; servers deserve better than this lol..
disallowed_names = {
    'cookiezi', 'rrtyui',
    'hvick225', 'qsc20010'
}

disallowed_passwords = {
    'password', 'minilamp'
}

# gulag provides connectivity to
# discord via a few simple webhooks.
# simply add urls to start receiving.
webhooks = {
    # general logging information
    'audit-log': '',

    # notifications of sketchy plays
    # & unusual activity auto-detected;
    # described in more detail below.
    'surveillance': '',

    # XXX: not a webhook, but the thumbnail used in them.
    'thumbnail': 'https://akatsuki.pw/static/logos/logo.png'
}

# gulag has begun to develop systems for detecting scores
# which the server deems as suspicious for any number of reasons.
# while some features may have a confidence threshold high enough
# to automatically ban players, the intention of this is mostly
# to make staff more aware of what's happening. below are some
# configurable values for what may trigger some parts of the
# system - if you don't know what it means, you shouldn't touch it!
surveillance = {
    'hitobj_low_presstimes': {
        # low presstimes on single hitobjects
        'value': 40, # ms
        'min_presses': 100
    },
}

# the max duration to
# cache a beatmap for.
# recommended: ~1 hour.
map_cache_timeout = 3600

# the max duration to cache
# osu-checkupdates requests for.
# recommended: ~1 hour.
updates_cache_timeout = 3600

# the pp values which should be cached & displayed when
# a user requests the general pp values for a beatmap.
pp_cached_accs = (90, 95, 98, 99, 100) # std & taiko
pp_cached_scores = (8e5, 8.5e5, 9e5, 9.5e5, 10e5) # mania

# https://datadoghq.com
# support (stats tracking)
datadog = {
    'api_key': '',
    'app_key': ''
}

# high ceiling values for autoban as a very simple form
# of "anticheat", simply ban a user if they are not
# whitelisted, and submit a score of too high caliber.
# Values below are in form (non_fl, fl), as fl has custom
# vals as it finds quite a few additional cheaters on the side.
autoban_pp = (
    (700,   600),   # vn!std
    (9999, 9999), # vn!taiko
    (9999, 9999), # vn!catch
    (9999, 9999), # vn!mania

    (1200,  800),   # rx!std
    (9999, 9999), # rx!taiko
    (9999, 9999), # rx!catch

    (9999, 9999)  # ap!std
)
