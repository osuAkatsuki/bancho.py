# -*- coding: utf-8 -*-

# Test server: 51.161.34.235
# (Only up once in a while now)
# (I mostly test this thing locally)

__all__ = ()

if __name__ != '__main__':
    raise Exception('main.py is meant to be run directly!')

import asyncio, uvloop
from aiohttp.client import ClientSession
from time import time
from os import chdir, path
from orjson import dumps

from cmyui.version import Version
from cmyui.mysql import AsyncSQLPool
from cmyui.web import (
    Address, HTTPStatus,
    AsyncConnection, AsyncTCPServer
)

from console import *
from handlers import *

from objects import glob
from objects.player import Player
from objects.channel import Channel
from constants.privileges import Privileges

from re import compile as re_comp
_bancho_re = re_comp(r'^c(?:e|[4-6])?\.ppy\.sh$')

# Set CWD to /gulag.
chdir(path.dirname(path.realpath(__file__)))

async def handle_conn(conn: AsyncConnection):
    if 'Host' not in conn.req.headers:
        await conn.resp.send(b'Missing required headers.',
                                HTTPStatus.BadRequest)
        return

    st = time()
    handler = None

    if _bancho_re.match(conn.req.headers['Host']):
        # Bancho handlers.
        if conn.req.uri == '/':
            handler = handle_bancho

    elif conn.req.headers['Host'] == 'osu.ppy.sh':
        # /web handlers, screenshots, and osu!direct downloads.
        if conn.req.startswith('/web/'):
            handler = handle_web
        elif conn.req.startswith('/ss/'):
            handler = handle_ss
        elif conn.req.startswith('/d/'):
            handler = handle_dl

    elif conn.req.headers['Host'] == 'a.ppy.sh':
        # Avatars.
        handler = handle_avatar

    if handler:
        # We have a handler for this request.
        await handler(conn)
    else:
        # We have no such handler.
        await plog(f'Unhandled {conn.req.uri}.', Ansi.LIGHT_RED)
        await conn.resp.send(b'Request handler not implemented.',
                             HTTPStatus.BadRequest)

    await plog(f'Handled in {1000 * (time() - st):.2f}ms', Ansi.LIGHT_CYAN)

async def run_server(loop: uvloop.Loop, addr: Address):
    glob.version = Version(2, 1, 2)
    glob.http = ClientSession(json_serialize=dumps) # use orjson for speed

    glob.db = AsyncSQLPool()
    await glob.db.connect(loop, **glob.config.mysql)

    # Aika
    glob.bot = Player(id = 1, name = 'Aika', priv = Privileges.Normal)
    glob.bot.ping_time = 0x7fffffff

    await glob.bot.stats_from_sql_full() # no need to get friends
    await glob.players.add(glob.bot)

    # Add all channels from db.
    for chan in await glob.db.fetchall('SELECT * FROM channels'):
        await glob.channels.add(Channel(**chan))

    async with AsyncTCPServer(addr) as serv:
        await plog(f'Gulag v{glob.version} online!', Ansi.LIGHT_GREEN)
        async for conn in serv.listen(loop, max_conns = 50):
            asyncio.create_task(handle_conn(conn))

# use uvloop for speed boost
loop = uvloop.new_event_loop()
asyncio.set_event_loop(loop)
loop.create_task(run_server(loop, glob.config.server_addr))

try:
    loop.run_forever()
finally:
    loop.close()
