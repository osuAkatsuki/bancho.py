# -*- coding: utf-8 -*-

# Test server: 51.161.34.235
# (Only up once in a while now)
# (I mostly test this thing locally)

__all__ = ()

if __name__ != '__main__':
    raise Exception('main.py is meant to be run directly!')

from time import time
from typing import Final
from os import chdir, path

from cmyui.web import TCPServer, Connection
from cmyui.version import Version
from cmyui.mysql import SQLPool

from console import *
from handlers import *

from objects import glob
from objects.player import Player
from objects.channel import Channel
from constants.privileges import Privileges

# Set CWD to /gulag.
chdir(path.dirname(path.realpath(__file__)))

glob.version: Final[Version] = Version(1, 4, 0)
glob.db = SQLPool(pool_size = 4, **glob.config.mysql)

# Aika
glob.bot = Player(id = 1, name = 'Aika', priv = Privileges.Normal)
glob.bot.ping_time = 0x7fffffff

glob.bot.stats_from_sql_full() # no need to get friends
glob.players.add(glob.bot)

# Add all channels from db.
for chan in glob.db.fetchall(
    'SELECT name, topic, read_priv, '
    'write_priv, auto_join FROM channels'
): glob.channels.add(Channel(**chan))

serv: TCPServer
conn: Connection

with TCPServer(glob.config.server_addr) as serv:
    printlog(f'Gulag v{glob.version} online!', Ansi.LIGHT_GREEN)
    for conn in serv.listen(max_conns = 5):
        st = time()

        handler = handle_bancho if conn.req.uri == '/' \
            else handle_web if conn.req.startswith('/web/') \
            else handle_ss if conn.req.startswith('/ss/') \
            else lambda *_: printlog(f'Unhandled {conn.req.uri}.', Ansi.LIGHT_RED)
        handler(conn)

        printlog(f'Request took {1000 * (time() - st):.2f}ms', Ansi.LIGHT_CYAN)
