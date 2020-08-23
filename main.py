# -*- coding: utf-8 -*-

# Test server: 51.161.34.235
# (Only up once in a while now)
# (I mostly test this thing locally)

__all__ = ()

if __name__ != '__main__':
    raise Exception('main.py is meant to be run directly!')

from aiohttp.client import ClientSession
import asyncio, uvloop
from cmyui.web import Address, AsyncConnection, AsyncTCPServer
from time import time
from os import chdir, path

#from cmyui.web import TCPServer, Connection
from cmyui.version import Version
from cmyui.mysql import AsyncSQLPool

from console import *
from handlers import *

from objects import glob
from objects.player import Player
from objects.channel import Channel
from constants.privileges import Privileges

async def run_server(loop: uvloop.Loop, addr: Address):
    # Set CWD to /gulag.
    chdir(path.dirname(path.realpath(__file__)))

    glob.version = Version(2, 0, 0)
    glob.http = ClientSession()

    glob.db = AsyncSQLPool()
    await glob.db.connect(loop, **glob.config.mysql)

    # Aika
    glob.bot = Player(id = 1, name = 'Aika', priv = Privileges.Normal)
    glob.bot.ping_time = 0x7fffffff

    await glob.bot.stats_from_sql_full() # no need to get friends
    glob.players.add(glob.bot)

    # Add all channels from db.
    for chan in await glob.db.fetchall('SELECT * FROM channels'):
        glob.channels.add(Channel(**chan))

    serv: AsyncTCPServer
    conn: AsyncConnection
    async with AsyncTCPServer(addr) as serv:
        printlog(f'Gulag v{glob.version} online!', Ansi.LIGHT_GREEN)
        async for conn in serv.listen(loop, max_conns = 50):
            st = time()

            handler = (handle_bancho if conn.req.uri == '/' # bancho handlers
                else handle_web if conn.req.startswith('/web/') # /web/* handlers
                else handle_ss if conn.req.startswith('/ss/') # screenshots
                else handle_dl if conn.req.startswith('/d/') # osu!direct
                else printlog(f'Unhandled {conn.req.uri}.', Ansi.LIGHT_RED))

            if handler:
                await handler(conn)

            printlog(f'Handled in {1000 * (time() - st):.2f}ms', Ansi.LIGHT_CYAN)

SOCKADDR = glob.config.server_addr

# use uvloop for speed boost
loop = uvloop.new_event_loop()
asyncio.set_event_loop(loop)
loop.create_task(run_server(loop, SOCKADDR))

try:
    loop.run_forever()
finally:
    loop.close()
