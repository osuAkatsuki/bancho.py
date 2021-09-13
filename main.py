#!/usr/bin/env python3.9

# if you're interested in development, my test server is usually
# up at https://c.cmyui.xyz. just use the same `-devserver cmyui.xyz`
# connection method you would with any other modern server and you
# should have no problems connecting. registration is done in-game
# with osu!'s built-in registration (if you're worried about not being
# properly connected while registering, the server should send back
# https://i.cmyui.xyz/8-Vzy9NllPBp5K7L.png if you use a random login).

# you can also test gulag's rest api using my test server,
# e.g https://osu.cmyui.xyz/api/get_player_scores?id=3&scope=best

import asyncio
import io
import os
import signal
import socket
import sys
from datetime import datetime
from pathlib import Path

import aiomysql
import cmyui
from cmyui.logging import log
from cmyui.logging import RGB

import bg_loops
import misc.utils
import misc.context
from constants.privileges import Privileges
from objects.achievement import Achievement
from objects.collections import Channels
from objects.collections import Clans
from objects.collections import MapPools
from objects.collections import Matches
from objects.collections import Players
from objects.player import Player

misc.utils._install_excepthook()

try:
    from objects import glob
except ModuleNotFoundError as exc:
    if exc.name == 'config':
        # the config module wasn't found,
        # create it as a copy of the sample config.
        misc.utils.create_config_from_default()
        raise SystemExit(1)
    else:
        raise

__all__ = ()

# current version of gulag
# NOTE: this is used internally for the updater, it may be
# worth reading through it's code before playing with it.
glob.version = cmyui.Version(3, 5, 4)

GEOLOC_DB_FILE = Path.cwd() / 'ext/GeoLite2-City.mmdb'

async def setup_collections(db_cursor: aiomysql.DictCursor) -> None:
    """Setup & cache the global collections before listening for connections."""
    # dynamic (active) sets, only in ram
    glob.matches = Matches()
    glob.players = Players()

    # static (inactive) sets, in ram & sql
    glob.channels = await Channels.prepare(db_cursor)
    glob.clans = await Clans.prepare(db_cursor)
    glob.pools = await MapPools.prepare(db_cursor)

    # create bot & add it to online players
    glob.bot = Player(
        id=1,
        name=await misc.utils.fetch_bot_name(db_cursor),
        login_time=float(0x7fffffff), # (never auto-dc)
        priv=Privileges.Normal,
        bot_client=True
    )
    glob.players.append(glob.bot)

    # global achievements (sorted by vn gamemodes)
    glob.achievements = []

    await db_cursor.execute('SELECT * FROM achievements')
    async for row in db_cursor:
        # NOTE: achievement conditions are stored as stringified python
        # expressions in the database to allow for extensive customizability.
        condition = eval(f'lambda score, mode_vn: {row.pop("cond")}')
        achievement = Achievement(**row, cond=condition)

        glob.achievements.append(achievement)

    # static api keys
    await db_cursor.execute(
        'SELECT id, api_key FROM users '
        'WHERE api_key IS NOT NULL'
    )
    glob.api_keys = {
        row['api_key']: row['id']
        async for row in db_cursor
    }

async def run_server() -> None:
    """Begin listening for and handling connections on all endpoints."""

    # we'll be working on top of transport layer posix sockets.
    # these implement tcp/ip over ethernet for us, and osu!stable
    # uses http/1.0 ontop of this. we'll need to parse the http data,
    # find the appropriate handler, and dispatch the connection.

    # i'll be using my light web framework to handle parsing & dispatching
    # of connections to their respective handlers; here, we'll just worry
    # about the socket-level details, like receiving the data from the clients.

    # if you're interested in more details, you can see the implementation at
    # https://github.com/cmyui/cmyui_pkg/blob/master/cmyui/web.py

    glob.app = cmyui.Server(
        name=f'gulag v{glob.version}',
        gzip=4, debug=glob.config.debug
    )

    # fetch our server's endpoints; gulag supports
    # osu!'s handlers across multiple domains.
    from domains.cho import domain as c_ppy_sh # /c[e4-6]?.ppy.sh/
    from domains.osu import domain as osu_ppy_sh
    from domains.ava import domain as a_ppy_sh
    from domains.map import domain as b_ppy_sh
    glob.app.add_domains({c_ppy_sh, osu_ppy_sh,
                            a_ppy_sh, b_ppy_sh})

    # support both INET and UNIX sockets
    if misc.utils.is_inet_address(glob.config.server_addr):
        sock_family = socket.AF_INET
    elif isinstance(glob.config.server_addr, str):
        sock_family = socket.AF_UNIX
    else:
        raise ValueError('Invalid socket address.')

    if sock_family == socket.AF_UNIX:
        # using unix socket - remove from filesystem if it exists
        if os.path.exists(glob.config.server_addr):
            os.remove(glob.config.server_addr)

    # create our transport layer socket; osu! uses tcp/ip
    with socket.socket(sock_family, socket.SOCK_STREAM) as listening_sock:
        listening_sock.setblocking(False) # asynchronous
        listening_sock.bind(glob.config.server_addr)

        if sock_family == socket.AF_UNIX:
            # using unix socket - give the socket file
            # appropriate (read, write) permissions
            os.chmod(glob.config.server_addr, 0o666)

        listening_sock.listen(glob.config.max_conns)
        log(f'-> Listening @ {glob.config.server_addr}', RGB(0x00ff7f))

        glob.ongoing_conns = []
        glob.shutting_down = False

        while not glob.shutting_down:
            # TODO: this timeout based-solution can be heavily
            #       improved and refactored out.
            try:
                conn, _ = await asyncio.wait_for(
                    fut=loop.sock_accept(listening_sock),
                    timeout=0.25
                )
            except asyncio.TimeoutError:
                pass
            else:
                task = loop.create_task(glob.app.handle(conn))
                task.add_done_callback(misc.utils._conn_finished_cb)
                glob.ongoing_conns.append(task)

    if sock_family == socket.AF_UNIX:
        # using unix socket - remove from filesystem
        os.remove(glob.config.server_addr)

async def main() -> int:
    """Initialize, and start up the server."""
    glob.loop = asyncio.get_running_loop()

    async with (
        misc.context.acquire_http_session(glob.has_internet) as glob.http_session,
        misc.context.acquire_mysql_db_pool(glob.config.mysql) as glob.db
    ):
        await misc.utils.check_for_dependency_updates()
        await misc.utils.update_mysql_structure()

        with (
            misc.context.acquire_geoloc_db_conn(GEOLOC_DB_FILE) as glob.geoloc_db,
            misc.context.acquire_datadog_client(glob.config.datadog) as glob.datadog
        ):
            # cache many global collections/objects from sql,
            # such as channels, mappools, clans, bot, etc.
            async with glob.db.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as db_cursor:
                    await setup_collections(db_cursor)

            # initialize housekeeping tasks to automatically
            # handle tasks such as disconnecting inactive players,
            # removing donator startus, etc.
            await bg_loops.initialize_tasks()

            # handle signals so we can ensure a graceful shutdown
            sig_handler = misc.utils.shutdown_signal_handler
            for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
                loop.add_signal_handler(signum, sig_handler, signum)

            # TODO: restart signal handler with SIGUSR1

            # run the server, handling connections
            # until a termination signal is received.
            await run_server()

            # we want to attempt to gracefully finish any ongoing connections
            # and shut down any of the housekeeping tasks running in the background.

            if glob.ongoing_conns:
                await misc.utils.await_ongoing_connections(timeout=5.0)

            await misc.utils.cancel_housekeeping_tasks()

    return 0

if __name__ == '__main__':
    """After basic safety checks, start the event loop and call our async entry point."""
    os.chdir(os.path.dirname(os.path.realpath(__file__))) # set cwd to /gulag

    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding='utf-8')

    for safety_check in (
        misc.utils.ensure_supported_platform, # linux only at the moment
        misc.utils.ensure_local_services_are_running, # mysql (if local)
        misc.utils.ensure_directory_structure, # .data/ & achievements/ dir structure
        misc.utils.ensure_dependencies_and_requirements # submodules & oppai-ng built
    ):
        if (exit_code := safety_check()) != 0:
            raise SystemExit(exit_code)

    """ Server should be safe to start """

    glob.boot_time = datetime.now()

    # install any debugging hooks from
    # _testing/runtime.py, if present
    misc.utils.__install_debugging_hooks()

    # check our internet connection status
    glob.has_internet = misc.utils.check_connection(timeout=1.5)

    # show info & any contextual warnings.
    misc.utils.display_startup_dialog()

    try:
        # use uvloop if available
        # https://github.com/MagicStack/uvloop
        import uvloop
        uvloop.install()
    except ModuleNotFoundError:
        pass

    loop = asyncio.new_event_loop()

    try:
        asyncio.set_event_loop(loop)
        raise SystemExit(loop.run_until_complete(main()))
    finally:
        try:
            misc.utils._cancel_all_tasks(loop)
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.run_until_complete(loop.shutdown_default_executor())
        finally:
            asyncio.set_event_loop(None)
            loop.close()

elif __name__ == 'main':
    # check specifically for ASGI servers; many related projects use
    # them to run in production, and devs may assume we do as well.
    if misc.utils.running_via_asgi_webserver():
        raise RuntimeError(
            "gulag implements it's own web framework implementation from "
            "transport layer (tcp/ip) posix sockets and does not rely on "
            "an ASGI server to serve connections; run it directy, `./main.py`"
        )
    else:
        raise RuntimeError('gulag should only be run directly, `./main.py`')
