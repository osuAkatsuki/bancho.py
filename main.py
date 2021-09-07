#!/usr/bin/env python3.9
# -*- coding: utf-8 -*-

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
import sys
from datetime import datetime
from pathlib import Path

import aiohttp
import aiomysql
import cmyui
import datadog
import orjson
import geoip2.database
import subprocess
from cmyui.logging import Ansi
from cmyui.logging import log

import bg_loops
import utils.misc
from constants.privileges import Privileges
from objects.achievement import Achievement
from objects.collections import Players
from objects.collections import Matches
from objects.collections import Channels
from objects.collections import Clans
from objects.collections import MapPools
from objects.player import Player
from utils.updater import Updater

__all__ = ()

# we print utf-8 content quite often
if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding='utf-8')

# set cwd to /gulag
os.chdir(os.path.dirname(os.path.realpath(__file__)))

try:
    from objects import glob
except ModuleNotFoundError as exc:
    if exc.name == 'config':
        # config file doesn't exist; create it from the default.
        import shutil
        shutil.copy('ext/config.sample.py', 'config.py')
        log('A config file has been generated, '
            'please configure it to your needs.', Ansi.LRED)
        raise SystemExit(1)
    else:
        raise

utils.misc.install_excepthook()

# current version of gulag
# NOTE: this is used internally for the updater, it may be
# worth reading through it's code before playing with it.
glob.version = cmyui.Version(3, 5, 4)

OPPAI_PATH = Path.cwd() / 'oppai-ng'
GEOLOC_DB_FILE = Path.cwd() / 'ext/GeoLite2-City.mmdb'
DEBUG_HOOKS_PATH = Path.cwd() / '_testing/runtime.py'
DATA_PATH = Path.cwd() / '.data'
ACHIEVEMENTS_ASSETS_PATH = DATA_PATH / 'assets/medals/client'

async def setup_collections(db_cursor: aiomysql.DictCursor) -> None:
    """Setup & cache many global collections."""
    # dynamic (active) sets, only in ram
    glob.players = Players()
    glob.matches = Matches()

    # static (inactive) sets, in ram & sql
    glob.channels = await Channels.prepare(db_cursor)
    glob.clans = await Clans.prepare(db_cursor)
    glob.pools = await MapPools.prepare(db_cursor)

    # create bot & add it to online players
    glob.bot = Player(
        id=1,
        name=await utils.misc.fetch_bot_name(db_cursor),
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

async def before_serving() -> None:
    """Called before the server begins serving connections."""
    glob.loop = asyncio.get_running_loop()

    if glob.has_internet:
        # retrieve a client session to use for http connections.
        glob.http = aiohttp.ClientSession(json_serialize=orjson.dumps) # type: ignore
    else:
        glob.http = None

    # retrieve a pool of connections to use for mysql interaction.
    glob.db = cmyui.AsyncSQLPool()
    await glob.db.connect(glob.config.mysql)

    # run the sql & submodule updater (uses http & db).
    # TODO: updating cmyui_pkg should run before it's import
    updater = Updater(glob.version)
    await updater.run()
    await updater.log_startup()

    # open a connection to our local geoloc database,
    # if the database file is present.
    if GEOLOC_DB_FILE.exists():
        glob.geoloc_db = geoip2.database.Reader(GEOLOC_DB_FILE)
    else:
        glob.geoloc_db = None

    # support for https://datadoghq.com
    if all(glob.config.datadog.values()):
        datadog.initialize(**glob.config.datadog)
        glob.datadog = datadog.ThreadStats()
        glob.datadog.start(flush_in_thread=True,
                           flush_interval=15)

        # wipe any previous stats from the page.
        glob.datadog.gauge('gulag.online_players', 0)
    else:
        glob.datadog = None

    new_coros = []

    # cache many global collections/objects from sql,
    # such as channels, mappools, clans, bot, etc.
    async with glob.db.pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as db_cursor:
            await setup_collections(db_cursor)

            # create a task for each donor expiring in 30d.
            new_coros.extend(await bg_loops.donor_expiry(db_cursor))

    # setup a loop to kick inactive ghosted players.
    new_coros.append(bg_loops.disconnect_ghosts())

    '''
    # if the surveillance webhook has a value, run
    # automatic (still very primitive) detections on
    # replays deemed by the server's configurable values.
    if glob.config.webhooks['surveillance']:
        new_coros.append(bg_loops.replay_detections())
    '''

    # reroll the bot's random status every `interval` sec.
    new_coros.append(bg_loops.reroll_bot_status(interval=300))

    for coro in new_coros:
        glob.app.add_pending_task(coro)

async def after_serving() -> None:
    """Called after the server stops serving connections."""
    if hasattr(glob, 'http') and glob.http is not None:
        await glob.http.close()

    if hasattr(glob, 'db') and glob.db.pool is not None:
        await glob.db.close()

    if hasattr(glob, 'geoloc_db') and glob.geoloc_db is not None:
        glob.geoloc_db.close()

    if hasattr(glob, 'datadog') and glob.datadog is not None:
        glob.datadog.stop()
        glob.datadog.flush()

def ensure_supported_platform() -> int:
    """Ensure we're running on an appropriate platform for gulag."""
    if sys.platform != 'linux':
        log('gulag currently only supports linux', Ansi.LRED)
        if sys.platform == 'win32':
            log("you could also try wsl(2), i'd recommend ubuntu 18.04 "
                "(i use it to test gulag)", Ansi.LBLUE)
        return 1

    if sys.version_info < (3, 9):
        log('gulag uses many modern python features, '
            'and the minimum python version is 3.9.', Ansi.LRED)
        return 1

    return 0

def ensure_local_services_are_running() -> int:
    """Ensure all required services (mysql) are running."""
    # NOTE: if you have any problems with this, please contact me
    # @cmyui#0425/cmyuiosu@gmail.com. i'm interested in knowing
    # how people are using the software so that i can keep it
    # in mind while developing new features & refactoring.

    if glob.config.mysql['host'] in ('localhost', '127.0.0.1', None):
        # sql server running locally, make sure it's running
        for service in ('mysqld', 'mariadb'):
            if os.path.exists(f'/var/run/{service}/{service}.pid'):
                break
        else:
            # not found, try pgrep
            pgrep_exit_code = os.system('pgrep mysqld')
            if pgrep_exit_code != 0:
                log('Please start your mysqld server.', Ansi.LRED)
                return 1

    return 0

def ensure_directory_structure() -> int:
    """Ensure the .data directory and git submodules are ready."""
    # create /.data and its subdirectories.
    DATA_PATH.mkdir(exist_ok=True)

    for sub_dir in ('avatars', 'logs', 'osu', 'osr', 'ss'):
        subdir = DATA_PATH / sub_dir
        subdir.mkdir(exist_ok=True)

    if not ACHIEVEMENTS_ASSETS_PATH.exists():
        if not glob.has_internet:
            # TODO: make it safe to run without achievements
            return 1

        ACHIEVEMENTS_ASSETS_PATH.mkdir(parents=True)
        utils.misc.download_achievement_images(ACHIEVEMENTS_ASSETS_PATH)

    return 0

def ensure_dependencies_and_requirements() -> int:
    """Make sure all of gulag's dependencies are ready."""
    if not OPPAI_PATH.exists():
        log('No oppai-ng submodule found, attempting to clone.', Ansi.LMAGENTA)
        p = subprocess.Popen(args=['git', 'submodule', 'init'],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        if exit_code := p.wait():
            log('Failed to initialize git submodules.', Ansi.LRED)
            return exit_code

        p = subprocess.Popen(args=['git', 'submodule', 'update'],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        if exit_code := p.wait():
            log('Failed to update git submodules.', Ansi.LRED)
            return exit_code

    if not (OPPAI_PATH / 'liboppai.so').exists():
        log('No oppai-ng library found, attempting to build.', Ansi.LMAGENTA)
        p = subprocess.Popen(args=['./libbuild'], cwd='oppai-ng',
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        if exit_code := p.wait():
            log('Failed to build oppai-ng automatically.', Ansi.LRED)
            return exit_code

    return 0

def __install_debugging_hooks() -> None:
    """Change internals to help with debugging & active development."""
    if DEBUG_HOOKS_PATH.exists():
        from _testing import runtime # type: ignore
        runtime.setup()

def display_startup_dialog() -> None:
    """Print any general information or warnings to the console."""
    if glob.config.advanced:
        log('running in advanced mode', Ansi.LRED)

    # running on root grants the software potentally dangerous and
    # unnecessary power over the operating system and is not advised.
    if os.geteuid() == 0:
        log('It is not recommended to run gulag as root, '
            'especially in production..', Ansi.LYELLOW)

        if glob.config.advanced:
            log('The risk is even greater with features '
                'such as config.advanced enabled.', Ansi.LRED)

    if not glob.has_internet:
        log('Running in offline mode, some features '
            'will not be available.', Ansi.LRED)

def main() -> int:
    for safety_check in (
        ensure_supported_platform, # linux only at the moment
        ensure_local_services_are_running, # mysql (if local)
        ensure_directory_structure, # .data/ & achievements/ dir structure
        ensure_dependencies_and_requirements # submodules & oppai-ng built
    ):
        if (exit_code := safety_check()) != 0:
            return exit_code

    '''Server is safe to start up'''

    glob.boot_time = datetime.now()

    # install any debugging hooks from
    # _testing/runtime.py, if present
    __install_debugging_hooks()

    # check our internet connection status
    glob.has_internet = utils.misc.check_connection(timeout=1.5)

    # show info & any contextual warnings.
    display_startup_dialog()

    # create the server object; this will handle http connections
    # for us via the transport (tcp/ip) socket interface, and will
    # handle housekeeping (setup, cleanup) for us automatically.
    glob.app = cmyui.Server(
        name=f'gulag v{glob.version}',
        gzip=4, debug=glob.config.debug
    )

    # add the domains and their respective endpoints to our server object
    from domains.cho import domain as cho_domain # c[e4-6]?.ppy.sh
    from domains.osu import domain as osu_domain # osu.ppy.sh
    from domains.ava import domain as ava_domain # a.ppy.sh
    from domains.map import domain as map_domain # b.ppy.sh
    glob.app.add_domains({cho_domain, osu_domain,
                        ava_domain, map_domain})

    # attach housekeeping tasks (setup, cleanup)
    glob.app.before_serving = before_serving
    glob.app.after_serving = after_serving

    # run the server (this is a blocking call)
    glob.app.run(addr=glob.config.server_addr,
                 handle_restart=True) # (using SIGUSR1)

    return 0

if __name__ == '__main__':
    raise SystemExit(main())
elif __name__ == 'main':
    # check specifically for asgi servers since many related projects
    # (such as gulag-web) use them, so people may assume we do as well.
    if utils.misc.running_via_asgi_webserver(sys.argv[0]):
        raise RuntimeError(
            "gulag does not use an ASGI framework, and uses it's own custom "
            "web framework implementation; please run it directly (./main.py)."
        )
    else:
        raise RuntimeError('gulag should only be run directly (./main.py).')
