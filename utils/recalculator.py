# -*- coding: utf-8 -*-

import asyncio
import hashlib
import math
import struct
from pathlib import Path
from typing import Optional
from typing import TYPE_CHECKING

import aiohttp
from cmyui import Ansi
from cmyui import log
from maniera.calculator import Maniera

if TYPE_CHECKING:
    from objects.beatmap import Beatmap

__all__ = ('PPCalculator',)

BEATMAPS_PATH = Path.cwd() / '.data/osu'

class PPCalculator:
    """Asynchronously wraps the process of calculating difficulty in osu!."""
    __slots__ = ('file', 'mode_vn', 'pp_attrs')
    def __init__(self, bmap: 'Beatmap', **pp_attrs) -> None:
        # NOTE: this constructor should not be called
        # unless you are CERTAIN the map is on disk
        # for normal usage, use the classmethods
        self.file = f'.data/osu/{bmap.id}.osu'

        if 'mode_vn' in pp_attrs:
            self.mode_vn = pp_attrs['mode_vn']
        else:
            self.mode_vn = 0

        self.pp_attrs = pp_attrs

    @staticmethod
    async def get_from_osuapi(bmap: 'Beatmap', dest_path: Path) -> bool:
        url = f'https://old.ppy.sh/osu/{bmap.id}'

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as r:
                if not r or r.status != 200:
                    log(f'Could not find map by id {bmap.id}!', Ansi.LRED)
                    return False

                content = await r.read()

        dest_path.write_bytes(content)
        return True

    @classmethod
    async def get_file(cls, bmap: 'Beatmap') -> Optional[Path]:
        path = BEATMAPS_PATH / f'{bmap.id}.osu'

        if (
            not path.exists() or
            bmap.md5 != hashlib.md5(path.read_bytes()).hexdigest()
        ):
            # map not up to date, we gotta update it
            if not await cls.get_from_osuapi(bmap, path):
                # failed to find the map
                return

        return path

    @classmethod
    async def from_map(cls, bmap: 'Beatmap', **pp_attrs) -> Optional['PPCalculator']:
        # ensure we have the file on disk for recalc
        if not await cls.get_file(bmap):
            return

        return cls(bmap, **pp_attrs)

    async def perform(self) -> tuple[float, float]:
        """Calculate pp & sr using the current state of the recalculator."""
        if self.mode_vn in (0, 1): # oppai-ng for std & taiko
            # TODO: PLEASE rewrite this with c/py bindings,
            # add ways to get specific stuff like aim pp

            # for now, we'll generate a bash command and
            # use subprocess to do the calculations (yikes).
            cmd = ['oppai-ng/oppai', self.file]

            if 'mods' in self.pp_attrs:
                cmd.append(f'+{self.pp_attrs["mods"]!r}')
            if 'combo' in self.pp_attrs:
                cmd.append(f'{self.pp_attrs["combo"]}x')
            if 'nmiss' in self.pp_attrs:
                cmd.append(f'{self.pp_attrs["nmiss"]}xM')
            if 'acc' in self.pp_attrs:
                cmd.append(f'{self.pp_attrs["acc"]:.4f}%')

            if self.mode_vn != 0:
                cmd.append(f'-m{self.mode_vn}')
                if self.mode_vn == 1:
                    cmd.append('-otaiko')

            cmd.append('-obinary')

            # run the oppai-ng binary & read stdout.
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE
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

            return (pp, sr)
        elif self.mode_vn == 2:
            # TODO: ctb support
            return (0.0, 0.0)
        elif self.mode_vn == 3: # use maniera for mania
            if 'score' not in self.pp_attrs:
                log('Err: pp calculator needs score for mania.', Ansi.LRED)
                return (0.0, 0.0)

            if 'mods' in self.pp_attrs:
                mods = int(self.pp_attrs['mods'])
            else:
                mods = 0

            calc = Maniera(self.file, mods, self.pp_attrs['score'])
            calc.calculate()
            return (calc.pp, calc.sr)
