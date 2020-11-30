#!/usr/bin/python3.9
# -*- coding: utf-8 -*-

# if you're interested in development, my test server is
# usually up at 51.161.34.235. just switch the ip of any
# switcher to the one above, toggle it off and on again, and
# you should be connected. registration is done ingame with
# osu!'s built-in registration.
# certificate: https://akatsuki.pw/static/ca.crt

__all__ = ()

import asyncio
import cmyui
import os

import aiohttp
import orjson # go zoom
import time

from objects import glob
from objects.player import Player
from objects.channel import Channel
from constants.privileges import Privileges

async def on_start() -> None:
    glob.version = cmyui.Version(2, 9, 0)
    glob.http = aiohttp.ClientSession(json_serialize=orjson.dumps)

    # connect to mysql
    glob.db = cmyui.AsyncSQLPool()
    await glob.db.connect(glob.config.mysql)

    # create our bot & append it to the global player list.
    glob.bot = Player(id=1, name='Aika', priv=Privileges.Normal)
    glob.bot.last_recv_time = 0x7fffffff

    glob.players.add(glob.bot)

    # add all channels from db.
    async for chan in glob.db.iterall('SELECT * FROM channels'):
        await glob.channels.add(Channel(**chan))

PING_TIMEOUT = 300000 // 10
async def disconnect_inactive() -> None:
    """Actively disconnect users above the
       disconnection time threshold on the osu! server."""
    while True:
        ctime = time.time()

        for p in glob.players:
            if ctime - p.last_recv_time > PING_TIMEOUT:
                await p.logout()

        # run this indefinitely
        await asyncio.sleep(30)

from domains.cho import domain as cho_domain # c[e4-6]?.ppy.sh
from domains.osu import domain as osu_domain # osu.ppy.sh
from domains.ava import domain as ava_domain # a.ppy.sh

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

    app = cmyui.Server(name='gulag', gzip=4, verbose=True)

    app.add_domains({cho_domain, osu_domain, ava_domain})
    app.add_tasks({on_start(), disconnect_inactive()})

    app.run('/tmp/gulag.sock') # blocking call
