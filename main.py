#!/usr/bin/python3.9
# -*- coding: utf-8 -*-

# if you're interested in development, my test server is
# usually up at 51.161.34.235. just switch the ip of any
# switcher to the one above, toggle it off and on again, and
# you should be connected. registration is done on login,
# so login with whatever credentials you'd like permanently.
# certificate: https://akatsuki.pw/static/ca.crt

__all__ = ()

import asyncio
import importlib
import aiohttp
import signal
import orjson # faster & more accurate than stdlib json
import time
import sys
import os
from cmyui import (Version, Address, Ansi, AnsiRGB, log,
                   AsyncConnection, AsyncTCPServer,
                   AsyncSQLPoolWrapper)

from handlers import *

from objects import glob
from objects.player import Player
from objects.channel import Channel
from constants.privileges import Privileges

async def handle_conn(conn: AsyncConnection) -> None:
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
            elif conn.path.startswith('/api/'):
                handler = handle_api
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
        log(f'Unhandled {conn.path}.', Ansi.LRED)
        await conn.send(400, b'Request handler not implemented.')

    if glob.config.debug:
        time_taken = (time.time_ns() - st) / 1000 # nanos -> micros
        time_str = (f'{time_taken:.2f}μs' if time_taken < 1000
               else f'{time_taken / 1000:.2f}ms')

        log(f'Request handled in {time_str}.', Ansi.LCYAN)

PING_TIMEOUT = 300000 // 10
async def disconnect_inactive() -> None:
    while True:
        ctime = time.time()

        for p in glob.players:
            if ctime - p.last_recv_time > PING_TIMEOUT:
                await p.logout()

        # run this indefinitely
        await asyncio.sleep(30)

async def run_server(addr: Address) -> None:
    glob.version = Version(2, 8, 5)
    glob.http = aiohttp.ClientSession(json_serialize=orjson.dumps)

    loop = asyncio.get_event_loop()

    try:
        loop.add_signal_handler(signal.SIGINT, loop.stop)
        loop.add_signal_handler(signal.SIGTERM, loop.stop)
    except NotImplementedError:
        pass

    glob.db = AsyncSQLPoolWrapper()
    await glob.db.connect(**glob.config.mysql)

    # create our bot & append it to the global player list.
    glob.bot = Player(id=1, name='Aika', priv=Privileges.Normal)
    glob.bot.last_recv_time = 0x7fffffff

    glob.players.add(glob.bot)

    # add all channels from db.
    async for chan in glob.db.iterall('SELECT * FROM channels'):
        await glob.channels.add(Channel(**chan))

    # run background process to
    # disconnect inactive clients.
    loop.create_task(disconnect_inactive())

    async with AsyncTCPServer(addr) as glob.serv:
        log(f'Gulag v{glob.version} online!', AnsiRGB(0x00ff7f))
        async for conn in glob.serv.listen(glob.config.max_conns):
            loop.create_task(handle_conn(conn))

if __name__ == '__main__':
    # set cwd to /gulag.
    os.chdir(os.path.dirname(os.path.realpath(__file__)))

    # make sure gulag/.data directory exists.
    if not os.path.isdir('.data'):
        os.mkdir('.data')

    # make sure that all gulag/.data subdirectories exist.
    for p in ('avatars', 'logs', 'osu', 'osr', 'ss'):
        if not os.path.isdir(f'.data/{p}'):
            os.mkdir(f'.data/{p}')

    # use uvloop if available (faster event loop).
    if spec := importlib.util.find_spec('uvloop'):
        uvloop = importlib.util.module_from_spec(spec)
        sys.modules['uvloop'] = uvloop
        spec.loader.exec_module(uvloop)

        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

    asyncio.run(run_server(glob.config.server_addr))
