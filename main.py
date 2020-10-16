#!/usr/bin/python3.9
# -*- coding: utf-8 -*-

# if you're interested in development, my test server is
# usually up at 51.161.34.235. just switch the ip of any
# switcher to the one above, toggle it off and on again, and
# you should be connected. registration is done on login,
# so login with whatever credentials you'd like permanently.
# certificate: https://akatsuki.pw/static/ca.crt

__all__ = ()

if __name__ != '__main__':
    raise Exception('main.py is meant to be run directly!')

import asyncio
import importlib
import aiohttp
import signal
import orjson # faster & more accurate than stdlib json
import cmyui # web & db
import time
import sys
import os

from console import *
from handlers import *

from objects import glob
from objects.player import Player
from objects.channel import Channel
from constants.privileges import Privileges

# set cwd to /gulag.
os.chdir(os.path.dirname(os.path.realpath(__file__)))

# make sure gulag/.data directory exists
if not os.path.isdir('.data'):
    os.mkdir('.data')

# make sure that all gulag/.data subdirectories exist
for p in ('avatars', 'logs', 'osu', 'osr', 'ss'):
    if not os.path.isdir(f'.data/{p}'):
        os.mkdir(f'.data/{p}')

async def handle_conn(conn: cmyui.AsyncConnection) -> None:
    if 'Host' not in conn.headers:
        await conn.send(400, b'Missing required headers.')
        return

    st = time.time_ns()
    handler = None

    domain = conn.headers['Host']

    # match the host & uri to the correct handlers.

    if domain.endswith('.ppy.sh'):
        # osu! handlers
        subdomain = domain.removesuffix('.ppy.sh')

        if subdomain in ('c', 'ce', 'c4', 'c5', 'c6'):
            # connection to `c[e4-6]?.ppy.sh/*`
            handler = handle_bancho
        elif subdomain == 'osu':
            # connection to `osu.ppy.sh/*`
            if conn.path.startswith('/web/'):
                handler = handle_web
            elif conn.path.startswith('/ss/'):
                handler = handle_ss
            elif conn.path.startswith('/d/'):
                handler = handle_dl
            elif conn.path == '/users':
                handler = handle_registration
        elif subdomain == 'a':
            handler = handle_avatar

    else:
        # non osu!-related handler
        if domain.endswith(glob.config.domain):
            if conn.path.startswith('/api/'):
                handler = handle_api # gulag!api
            else:
                # frontend handler?
                ...
        else:
            # nginx sending something that we're not handling?
            ...

    if handler:
        # we have a handler for this request.
        await handler(conn)
    else:
        # we have no such handler.
        plog(f'Unhandled {conn.path}.', Ansi.LRED)
        await conn.send(400, b'Request handler not implemented.')

    if glob.config.debug:
        time_taken = (time.time_ns() - st) / 1000 # nanos -> micros
        time_str = (f'{time_taken:.2f}μs' if time_taken < 1000
               else f'{time_taken / 1000:.2f}ms')

        plog(f'Request handled in {time_str}.', Ansi.LCYAN)

async def run_server(addr: cmyui.Address) -> None:
    glob.version = cmyui.Version(2, 7, 5)
    glob.http = aiohttp.ClientSession(json_serialize=orjson.dumps)

    loop = asyncio.get_event_loop()

    try:
        loop.add_signal_handler(signal.SIGINT, lambda: loop.stop())
        loop.add_signal_handler(signal.SIGTERM, lambda: loop.stop())
    except NotImplementedError:
        pass

    glob.db = cmyui.AsyncSQLPoolWrapper()
    await glob.db.connect(**glob.config.mysql)

    # create our bot & append it to the global player list.
    glob.bot = Player(id = 1, name = 'Aika', priv = Privileges.Normal)
    glob.bot.ping_time = 0x7fffffff

    await glob.players.add(glob.bot)

    # add all channels from db.
    async for chan in glob.db.iterall('SELECT * FROM channels'):
        await glob.channels.add(Channel(**chan))

    async with cmyui.AsyncTCPServer(addr) as glob.serv:
        plog(f'Gulag v{glob.version} online!', Ansi.LGREEN)
        async for conn in glob.serv.listen(glob.config.max_conns):
            asyncio.create_task(handle_conn(conn))

# use uvloop if available (faster event loop).
if spec := importlib.util.find_spec('uvloop'):
    uvloop = importlib.util.module_from_spec(spec)
    sys.modules['uvloop'] = uvloop
    spec.loader.exec_module(uvloop)

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

asyncio.run(run_server(glob.config.server_addr))
