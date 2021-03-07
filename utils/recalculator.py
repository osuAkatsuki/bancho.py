# -*- coding: utf-8 -*-

import asyncio
import math
import struct
from pathlib import Path

import aiohttp
from cmyui import Ansi
from cmyui import log

from constants.mods import Mods

__all__ = ('PPCalculator',)

BEATMAPS_PATH = Path.cwd() / '.data/osu'

class PPCalculator:
    """Asynchronously wraps the process of calculating difficulty in osu!."""
    def __init__(self, map_id: int, **kwargs) -> None:
        # NOTE: this constructor should not be called
        # unless you are CERTAIN the map is on disk
        # for normal usage, use the classmethods
        self.file = f'.data/osu/{map_id}.osu'

        self.mods = kwargs.get('mods', Mods.NOMOD)
        self.combo = kwargs.get('combo', 0)
        self.nmiss = kwargs.get('nmiss', 0)
        self.mode_vn = kwargs.get('mode_vn', 0)
        self.acc = kwargs.get('acc', 100.00)

    @staticmethod
    async def get_from_osuapi(map_id: int, dest_path: Path) -> bool:
        url = f'https://old.ppy.sh/osu/{map_id}'

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as r:
                if not r or r.status != 200:
                    log(f'Could not find map by id {map_id}!', Ansi.LRED)
                    return False

                content = await r.read()

        dest_path.write_bytes(content)
        return True

    @classmethod
    async def get_file(cls, map_id: int) -> None:
        path = BEATMAPS_PATH / f'{map_id}.osu'

        # check if file exists on disk already
        if not path.exists():
            # not found on disk, try osu!api
            if not await cls.get_from_osuapi(map_id, path):
                # failed to find the map
                return

        # map is now on disk, return filepath.
        return path

    @classmethod
    async def from_id(cls, map_id: int, **kwargs):
        # ensure we have the file on disk for recalc
        if not await cls.get_file(map_id):
            return

        return cls(map_id, **kwargs)

    async def perform(self) -> tuple[float, float]:
        """Perform the calculations with the current state, returning (pp, sr)."""
        # TODO: PLEASE rewrite this with c bindings,
        # add ways to get specific stuff like aim pp

        # for now, we'll generate a bash command and
        # use subprocess to do the calculations (yikes).
        cmd = [f'oppai-ng/oppai', self.file]

        if self.mods:  cmd.append(f'+{self.mods!r}')
        if self.combo: cmd.append(f'{self.combo}x')
        if self.nmiss: cmd.append(f'{self.nmiss}xM')
        if self.acc:   cmd.append(f'{self.acc:.4f}%')

        if self.mode_vn:
            if self.mode_vn not in (0, 1):
                # oppai-ng only supports std & taiko
                # TODO: osu!catch & mania support
                return (0.0, 0.0)

            cmd.append(f'-m{self.mode_vn}')
            if self.mode_vn == 1:
                cmd.append('-otaiko')

        cmd.append('-obinary')

        # run the oppai-ng binary & read stdout.
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout = asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate() # stderr not needed

        if stdout[:8] != b'binoppai':
            # invalid output from oppai-ng
            log(f'oppai-ng err: {stdout}', Ansi.LRED)
            return (0.0, 0.0)

        err_code = struct.unpack('<i', stdout[11:15])[0]

        if err_code < 0:
            log(f'oppai-ng: err code {err_code}.', Ansi.LRED)
            return (0.0, 0.0)

        pp = struct.unpack('<f', stdout[-4:])[0]

        if math.isinf(pp):
            log(f'oppai-ng: broken map: {self.file} (inf pp).', Ansi.LYELLOW)
            return (0.0, 0.0)

        sr = struct.unpack('<f', stdout[-32:-28])[0]

        return pp, sr
