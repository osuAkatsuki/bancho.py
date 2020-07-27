# -*- coding: utf-8 -*-

# Test server: 51.161.34.235
# (Only up once in a while now)
# (I mostly test this thing locally)

__all__ = ()

if __name__ != '__main__':
    raise Exception('main.py is meant to be run directly!')

from socket import AF_UNIX, SOCK_STREAM
from time import time
from typing import Final

from cmyui.web import TCPServer, Connection
from cmyui.version import Version
from cmyui.mysql import SQLPool

from console import *
from handlers import *

from objects import glob
from objects.player import Player
from objects.channel import Channel
from constants.privileges import Privileges

glob.version: Final[Version] = Version(1, 0, 0)
glob.db = SQLPool(pool_size = 4, **glob.config.mysql)

# Aika
glob.bot = Player(id = 1, name = 'Aika', priv = Privileges.Admin)
glob.bot.ping_time = 0x7fffffff

glob.bot.stats_from_sql_full() # no need to get friends
glob.players.add(glob.bot)

# Default channels.
# At some point, this will either be moved
# to db, or possibly just configration.
glob.channels.add(Channel(
    name = '#osu',
    topic = 'General discussion.',
    read = Privileges.Verified,
    write = Privileges.Verified,
    auto_join = True))
glob.channels.add(Channel(
    name = '#announce',
    topic = 'Exceptional performance & announcements.',
    read = Privileges.Verified,
    write = Privileges.Admin,
    auto_join = True))
glob.channels.add(Channel(
    name = '#lobby',
    topic = 'Multiplayer lobby chat.',
    read = Privileges.Verified,
    write = Privileges.Verified,
    auto_join = False))

serv: TCPServer
conn: Connection

with TCPServer('/tmp/gulag.sock') as serv:
    printlog(f'Gulag {glob.version} online!', Ansi.LIGHT_GREEN)
    for conn in serv.listen(max_conns = 5):
        st = time()

        handler = handle_bancho if conn.req.uri == '/' \
            else handle_web if conn.req.startswith('/web/') \
            else lambda *_: printlog(f'Unhandled {conn.req.uri}.', Ansi.LIGHT_RED)
        handler(conn)

        printlog(f'Packet took {1000 * (time() - st):.2f}ms', Ansi.LIGHT_CYAN)
