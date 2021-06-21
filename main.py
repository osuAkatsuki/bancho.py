#!/usr/bin/env python3.9
# -*- coding: utf-8 -*-

# if you're interested in development, my test server is usually
# up at https://c.cmyui.xyz. just use the same `-devserver cmyui.xyz`
# connection method you would with any other modern server and you
# should have no problems connecting. registration is done in-game
# with osu!'s built-in registration. the api can also be tested here,
# e.g https://osu.cmyui.xyz/api/get_player_scores?id=3&scope=best

import asyncio
import io
import os
import sys
from pathlib import Path

import aiohttp
import aiomysql
import cmyui
import datadog
import orjson # go zoom
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
        import shutil
        shutil.copy('ext/config.sample.py', 'config.py')
        sys.exit('\x1b[0;92mA config file has been generated, '
                 'please configure it to your needs.\x1b[0m')
    else:
        raise

utils.misc.install_excepthook()

# current version of gulag
# NOTE: this is used internally for the updater, it may be
# worth reading through it's code before playing with it.
glob.version = cmyui.Version(3, 4, 1)

OPPAI_PATH = Path.cwd() / 'oppai-ng'
GEOLOC_DB_FILE = Path.cwd() / 'ext/GeoLite2-City.mmdb'

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
    glob.loop = asyncio.get_event_loop()

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

    # cache many global collections/objects from sql,
    # such as channels, mappools, clans, bot, etc.
    async with glob.db.pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as db_cursor:
            await setup_collections(db_cursor)

    new_coros = []

    # create a task for each donor expiring in 30d.
    new_coros.extend(await bg_loops.donor_expiry())

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

def detect_mysqld_running() -> bool:
    """Detect whether theres a mysql server running locally."""
    for service in ('mysqld', 'mariadb'):
        if os.path.exists(f'/var/run/mysqld/{service}.pid'):
            return True
    else:
        # not found, try pgrep
        return os.system('pgrep mysqld') == 0

def ensure_platform() -> None:
    """Ensure we're running on an appropriate platform for gulag."""
    if sys.platform != 'linux':
        log('gulag currently only supports linux', Ansi.LRED)
        if sys.platform == 'win32':
            log("you could also try wsl(2), i'd recommend ubuntu 18.04 "
                "(i use it to test gulag)", Ansi.LBLUE)
        sys.exit()

    if sys.version_info < (3, 9):
        sys.exit('gulag uses many modern python features, '
                 'and the minimum python version is 3.9.')

def ensure_services() -> None:
    """Ensure all required services are running in the background."""
    # make sure nginx & mysqld are running.
    if (
        glob.config.mysql['host'] in ('localhost', '127.0.0.1') and
        not detect_mysqld_running()
    ):
        sys.exit('Please start your mysqld server.')

    if not os.path.exists('/var/run/nginx.pid'):
        sys.exit('Please start your nginx server.')

def _install_cmyui_dev_hooks():
    """Change internals to help with debugging & active development."""
    from _testing import runtime
    runtime.setup()

if __name__ == '__main__':
    """Attempt to start up gulag."""
    # make sure we're running on an appropriate
    # platform with all required software.
    ensure_platform()

    # make sure all required services
    # are being run in the background.
    ensure_services()

    if glob.config.advanced:
        log('running in advanced mode', Ansi.LRED)

    # warn the user if gulag is running on root.
    if os.geteuid() == 0:
        log('It is not recommended to run gulag as root, '
            'especially in production..', Ansi.LYELLOW)

        if glob.config.advanced:
            log('The risk is even greater with features '
                'such as config.advanced enabled.', Ansi.LRED)

    # check whether we are connected to the internet.
    glob.has_internet = utils.misc.check_connection(timeout=1.5)
    if not glob.has_internet:
        log('Running in offline mode, some features '
            'will not be available.', Ansi.LRED)

    # create /.data and its subdirectories.
    data_path = Path.cwd() / '.data'
    data_path.mkdir(exist_ok=True)

    for sub_dir in ('avatars', 'logs', 'osu', 'osr', 'ss'):
        subdir = data_path / sub_dir
        subdir.mkdir(exist_ok=True)

    achievements_path = data_path / 'assets/medals/client'
    if not achievements_path.exists():
        # create directory & download achievement images
        achievements_path.mkdir(parents=True)
        utils.misc.download_achievement_images(achievements_path)

    # make sure oppai-ng binary is built and ready.
    if not OPPAI_PATH.exists():
        log('No oppai-ng submodule found, attempting to clone.', Ansi.LMAGENTA)
        p = subprocess.Popen(args=['git', 'submodule', 'init'],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        if p.wait() == 1:
            sys.exit('Failed to initialize git submodules.')

        p = subprocess.Popen(args=['git', 'submodule', 'update'],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        if p.wait() == 1:
            sys.exit('Failed to update git submodules.')

    if not (OPPAI_PATH / 'oppai').exists():
        log('No oppai-ng binary found, attempting to build.', Ansi.LMAGENTA)
        p = subprocess.Popen(args=['./build'], cwd='oppai-ng',
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        if p.wait() == 1:
            sys.exit('Failed to build oppai-ng automatically.')

    # create a server object, which serves as a map of domains.
    app = glob.app = cmyui.Server(
        name=f'gulag v{glob.version}',
        gzip=4, debug=glob.config.debug
    )

    # add our endpoint's domains to the server;
    # each may potentially hold many individual endpoints.
    from domains.cho import domain as cho_domain # c[e4-6]?.ppy.sh
    from domains.osu import domain as osu_domain # osu.ppy.sh
    from domains.ava import domain as ava_domain # a.ppy.sh
    from domains.map import domain as map_domain # b.ppy.sh
    app.add_domains({cho_domain, osu_domain,
                     ava_domain, map_domain})

    # enqueue tasks to run once the server
    # begins, and stops serving connections.
    # these make sure we set everything up
    # and take it down nice and graceful.
    app.before_serving = before_serving
    app.after_serving = after_serving

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

    # cmyui-specific dev hooks, you can ignore this :)
    if os.getenv('cmyuiosu') is not None:
        _install_cmyui_dev_hooks()

    # start up the server; this starts an event loop internally,
    # using uvloop if it's installed. it uses SIGUSR1 for restarts.
    # NOTE: eventually the event loop creation will likely be
    # moved into the gulag codebase for increased flexibility.
    app.run(glob.config.server_addr, handle_restart=True)

elif __name__ == 'main':
    # check specifically for asgi servers since many related projects
    # (such as gulag-web) use them, so people may assume we do as well.
    if any([sys.argv[0].endswith(x) for x in ('hypercorn', 'uvicorn')]):
        raise RuntimeError(
            "gulag does not use an ASGI framework, and uses it's own custom "
            "web framework implementation; please run it directly (./main.py)."
        )
    else:
        raise RuntimeError('gulag should only be run directly (./main.py).')
