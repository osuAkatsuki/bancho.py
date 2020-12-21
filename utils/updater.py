# -*- coding: utf-8 -*-

# this file is for management of gulag version updates;
# it will automatically keep track of your running version,
# and when it detects a change, it will apply any nescessary
# changes to your sql database & keep cmyui_pkg up to date.

from importlib.metadata import version
from pip._internal.cli.main import main as pip_main
from typing import Optional
from cmyui import Version, log, Ansi
from pathlib import Path
from datetime import datetime as dt
from collections import defaultdict
import re

from objects import glob

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
            return Version.from_str(list(json['releases'])[-1])

    async def _update_cmyui(self) -> None:
        """Check if cmyui_pkg has a newer release; update if available."""
        module_ver = Version.from_str(version('cmyui'))
        latest_ver = await self._get_latest_cmyui()

        if module_ver < latest_ver:
            # package is not up to date; update it.
            log(f'Updating cmyui_pkg (v{module_ver!r} -> '
                                    f'v{latest_ver!r}).', Ansi.MAGENTA)
            pip_main(['install', '-Uq', 'cmyui']) # Update quiet

    async def _update_sql(self, prev_version: Version) -> None:
        """Apply any structural changes to the database since the last startup."""
        if self.version == prev_version:
            # already up to date.
            return

        # needs update, find all updates since prev_version
        log(f'Updating sql (v{prev_version!r} -> '
                          f'v{self.version!r}).', Ansi.MAGENTA)
        with open(SQL_UPDATES_FILE, 'r') as f:
            content = f.read()

        updates = defaultdict(list)
        current_ver = None

        for line in content.splitlines():
            if line.startswith('#') or not current_ver:
                # may be normal comment or new version
                if rgx := re.fullmatch(r'^# v(?P<ver>\d+\.\d+\.\d+)$', line):
                    current_ver = Version.from_str(rgx['ver'])

                continue

            updates[current_ver].append(line)

        # now go through updates, running the ones
        # between the previous and new versions.
        for update_ver, update_lines in updates.items():
            if prev_version < update_ver <= self.version:
                await glob.db.execute('\n'.join(update_lines))

    # TODO _update_config?
