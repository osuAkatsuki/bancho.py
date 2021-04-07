# -*- coding: utf-8 -*-

# this file is for management of gulag version updates;
# it will automatically keep track of your running version,
# and when it detects a change, it will apply any nescessary
# changes to your sql database & keep cmyui_pkg up to date.

import asyncio
import re
import os
import signal
from datetime import datetime as dt
from importlib.metadata import version as pkg_version
from pathlib import Path
from typing import Optional

import aiomysql
from cmyui import Ansi
from cmyui import log
from cmyui import Version
from pip._internal.cli.main import main as pip_main

from objects import glob

__all__ = ('Updater',)

SQL_UPDATES_FILE = Path.cwd() / 'ext/updates.sql'

class Updater:
    def __init__(self, version: Version) -> None:
        self.version = version

    async def run(self) -> None:
        """Prepare, and run the updater."""
        prev_ver = await self.get_prev_version()# or self.version

        if not prev_ver:
            # first time running the server.
            # might add other code here eventually..
            prev_ver = self.version

        await self._update_cmyui() # pip install -U cmyui
        await self._update_sql(prev_ver)

    @staticmethod
    async def get_prev_version() -> Optional[Version]:
        """Get the last launched version of the server."""
        res = await glob.db.fetch(
            'SELECT ver_major, ver_minor, ver_micro '
            'FROM startups ORDER BY datetime DESC LIMIT 1',
            _dict=False # get tuple
        )

        if res:
            return Version(*map(int, res))

    async def log_startup(self):
        """Log this startup to sql for future use."""
        ver = self.version
        await glob.db.execute(
            'INSERT INTO startups '
            '(ver_major, ver_minor, ver_micro, datetime) '
            'VALUES (%s, %s, %s, %s)',
            [ver.major, ver.minor, ver.micro, dt.now()]
        )

    async def _get_latest_cmyui(self) -> Version:
        """Get the latest version release of cmyui_pkg from pypi."""
        url = 'https://pypi.org/pypi/cmyui/json'
        async with glob.http.get(url) as resp:
            if not resp or resp.status != 200:
                return self.version

            # safe cuz py>=3.7 dicts are ordered
            if not (json := await resp.json()):
                return self.version

            # return most recent release version
            return Version.from_str(json['info']['version'])

    async def _update_cmyui(self) -> None:
        """Check if cmyui_pkg has a newer release; update if available."""
        module_ver = Version.from_str(pkg_version('cmyui'))
        latest_ver = await self._get_latest_cmyui()

        if module_ver < latest_ver:
            # package is not up to date; update it.
            log(f'Updating cmyui_pkg (v{module_ver!r} -> '
                                    f'v{latest_ver!r}).', Ansi.LMAGENTA)
            pip_main(['install', '-Uq', 'cmyui']) # Update quiet

    async def _update_sql(self, prev_version: Version) -> None:
        """Apply any structural changes to sql since the last startup."""
        if self.version == prev_version:
            # already up to date.
            return

        # version changed; there may be sql changes.
        content = SQL_UPDATES_FILE.read_text()

        queries = []
        q_lines = []

        current_ver = None

        for line in content.splitlines():
            if not line:
                continue

            if line.startswith('#'):
                # may be normal comment or new version
                if rgx := re.fullmatch(r'^# v(?P<ver>\d+\.\d+\.\d+)$', line):
                    current_ver = Version.from_str(rgx['ver'])

                continue
            elif not current_ver:
                continue

            # we only need the updates between the
            # previous and new version of the server.
            if prev_version < current_ver <= self.version:
                if line.endswith(';'):
                    if q_lines:
                        q_lines.append(line)
                        queries.append(' '.join(q_lines))
                        q_lines = []
                    else:
                        queries.append(line)
                else:
                    q_lines.append(line)

        if not queries:
            return

        log(f'Updating sql (v{prev_version!r} -> '
                          f'v{self.version!r}).', Ansi.LMAGENTA)

        sql_lock = asyncio.Lock()

        # TODO: sql transaction? for rollback
        async with sql_lock:
            for query in queries:
                try:
                    await glob.db.execute(query)
                except aiomysql.MySQLError:
                    # if anything goes wrong while writing a query,
                    # most likely something is very wrong.
                    log(f'Failed: {query}', Ansi.GRAY)
                    log(
                        "SQL failed to update - unless you've been modifying "
                        "sql and know what caused this, please please contact "
                        "cmyui#0425.", Ansi.LRED
                    )

                    input('Press enter to exit')
                    os.kill(os.getpid(), signal.SIGTERM)

    # TODO _update_config?
