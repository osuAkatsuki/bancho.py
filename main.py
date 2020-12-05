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
import os
import aiohttp
import orjson # go zoom
import time

import cmyui
from cmyui import log, Ansi

from objects import glob
from objects.player import Player
from objects.channel import Channel
from objects.match import MapPool

from constants.privileges import Privileges

async def on_start() -> None:
    glob.version = cmyui.Version(3, 0, 0)
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

    # add all mappools from db.
    async for pool in glob.db.iterall('SELECT * FROM tourney_pools'):
        # overwrite basic types with some class types
        pool['created_by'] = await glob.players.get_by_id(pool['created_by'], sql=True)

        pool = MapPool(**pool)
        await pool.maps_from_sql()
        await glob.pools.add(pool)

    # add new donation ranks & enqueue tasks to remove current ones.
    # TODO: this system can get quite a bit better; rather than just
    # removing, it should rather update with the new perks (potentially
    # a different tier, enqueued after their current perks).

    async def rm_donor(userid: int, delay: int):
        await asyncio.sleep(delay)

        p = await glob.players.get_by_id(userid, sql=True)
        p.remove_priv(Privileges.Donator)

        log(f"{p}'s donation perks have expired.", Ansi.MAGENTA)

    query = ('SELECT id, donor_end FROM users '
             'WHERE donor_end > UNIX_TIMESTAMP()')

    async for donation in glob.db.iterall(query):
        # calculate the delta between now & the exp date.
        delta = donation['donor_end'] - time.time()

        if delta > (60 * 60 * 24 * 30):
            # ignore donations expiring in over a months time;
            # the server should restart relatively often anyways.
            continue

        asyncio.create_task(rm_donor(donation['id'], delta))

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
