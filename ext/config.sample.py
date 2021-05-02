# -*- coding: utf-8 -*-

# this file should generally become
# less useful as you scroll down.
# except for the bottom one :P <3

""" server settings """
# the domain you'd like gulag to be hosted on.
domain = 'cmyui.xyz' # cmyui.xyz

# the address which the server runs on, unix or inet4.
server_addr = '/tmp/gulag.sock' # /tmp/gulag.sock,
                                # ('127.0.0.1', 1234)

# your mysql authentication info.
mysql = {
    'db': 'cmyui',
    'host': 'localhost',
    'password': 'lol123',
    'user': 'cmyui'
}

# your osu!api key, required for beatmap info.
osu_api_key = ''

# url of the mirror to use, for beatmap downloads.
mirror = 'https://api.chimu.moe/v1' # https://api.chimu.moe/v1

# in-game bot command prefix.
command_prefix = '!'

# the max amount of concurrent
# connections gulag will hold.
max_conns = 16 # likely ~8-16, depending on playercount & api usage

# the console gets a whole lot louder.
# devs can also toggle ingame w/ !debug.
debug = False

# the menu icon displayed on
# the main menu of osu! in-game.
menu_icon = (
    'https://akatsuki.pw/static/logos/logo_ingame.png', # image url
    'https://akatsuki.pw' # onclick url
)

# seasonal backgrounds to be displayed ingame.
seasonal_bgs = ('https://akatsuki.pw/static/flower.png',)

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

    ''' (currently unused)
    # notifications of sketchy plays
    # & unusual activity auto-detected;
    # described in more detail below.
    'surveillance': '',
    '''

    # XXX: not a webhook, but the thumbnail used in them.
    'thumbnail': 'https://akatsuki.pw/static/logos/logo.png'
}

# https://datadoghq.com
# support (stats tracking)
datadog = {
    'api_key': '',
    'app_key': ''
}

# the pp values which should be cached & displayed when
# a user requests the general pp values for a beatmap.
pp_cached_accs = (90, 95, 98, 99, 100) # std & taiko
pp_cached_scores = (8e5, 8.5e5, 9e5, 9.5e5, 10e5) # mania

# whether osu! client urls such as https://osu.your.domain/beatmaps/123
# should be redirected to osu.ppy.sh (https://osu.ppy.sh/beatmaps/123).
redirect_osu_urls = False

# the max duration to cache a beatmap for.
map_cache_timeout = 3600 # ~3600

# the max duration to cache osu-checkupdates requests for.
# NOTE: this is only required for switchers and will be removed.
updates_cache_timeout = 3600 # ~3600

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

# allow for use of advanced (and potentially dangerous)
# features. i recommend checking where this config value
# is used throughout the code before enabling it.. :P
advanced = False

# additional info: https://pastebin.com/u4u14bAb
automatically_report_problems = False
