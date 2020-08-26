# -*- coding: utf-8 -*-

# If you're interested in development, my test server is often up
# at 51.161.34.235 - registration is done on login, so login with
# whatever username you'd like; the cert is Akatsuki's.

__all__ = ()

if __name__ != '__main__':
    raise Exception('main.py is meant to be run directly!')

import asyncio
import uvloop # faster than stdlib asyncio event loop
import aiohttp
import orjson # faster & more accurate than stdlib json
import cmyui # web & db
import time
import os
import re

from console import *
from handlers import *

from objects import glob
from objects.player import Player
from objects.channel import Channel
from constants.privileges import Privileges

_bancho_re = re.compile(r'^c(?:e|[4-6])?\.ppy\.sh$')

# Set CWD to /gulag.
os.chdir(os.path.dirname(os.path.realpath(__file__)))

async def handle_conn(conn: cmyui.AsyncConnection):
    if 'Host' not in conn.req.headers:
        await conn.resp.send(b'Missing required headers.',
                             HTTPStatus.BadRequest)
        return

    st = time.time_ns()
    handler = None

    if _bancho_re.match(conn.req.headers['Host']):
        # Bancho handlers.
        if conn.req.path == '/':
            handler = handle_bancho

    elif conn.req.headers['Host'] == 'osu.ppy.sh':
        # /web handlers, screenshots, and osu!direct downloads.
        if conn.req.startswith('/web/'):
            handler = handle_web
        elif conn.req.startswith('/ss/'):
            handler = handle_ss
        elif conn.req.startswith('/d/'):
            handler = handle_dl
        elif conn.req.startswith('/api/'):
            handler = handle_api

    elif conn.req.headers['Host'] == 'a.ppy.sh':
        # Avatars.
        handler = handle_avatar

    if handler:
        # We have a handler for this request.
        await handler(conn)
    else:
        # We have no such handler.
        await plog(f'Unhandled {conn.req.path}.', Ansi.LIGHT_RED)
        await conn.resp.send(b'Request handler not implemented.',
                             cmyui.HTTPStatus.BadRequest)

    time_taken = (time.time_ns() - st) / 1000 # nanos -> micros
    time_str = (f'{time_taken:.2f}μs' if time_taken < 1000
           else f'{time_taken / 1000:.2f}ms')

    await plog(f'Handled in {time_str}.', Ansi.LIGHT_CYAN)

async def run_server(loop: uvloop.Loop, addr: cmyui.Address):
    glob.version = cmyui.Version(2, 2, 1)
    glob.http = aiohttp.ClientSession(json_serialize=orjson.dumps)

    glob.db = cmyui.AsyncSQLPool()
    await glob.db.connect(loop, **glob.config.mysql)

    # Aika
    glob.bot = Player(id = 1, name = 'Aika', priv = Privileges.Normal)
    glob.bot.ping_time = 0x7fffffff

    await glob.bot.stats_from_sql_full() # no need to get friends
    await glob.players.add(glob.bot)

    # Add all channels from db.
    async for chan in glob.db.iterall('SELECT * FROM channels'):
        await glob.channels.add(Channel(**chan))

    async with cmyui.AsyncTCPServer(addr) as serv:
        await plog(f'Gulag v{glob.version} online!', Ansi.LIGHT_GREEN)
        async for conn in serv.listen(loop, glob.config.max_conns):
            asyncio.create_task(handle_conn(conn))

# Create the event loop & run the server.
loop = uvloop.new_event_loop()
asyncio.set_event_loop(loop)
loop.create_task(run_server(loop, glob.config.server_addr))

try:
    loop.run_forever()
finally:
    loop.close()
