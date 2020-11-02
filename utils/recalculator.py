# -*- coding: utf-8 -*-

import asyncio
import aiofiles
import aiohttp
import orjson
import os
from cmyui import log, Ansi

from constants.gamemodes import GameMode
from constants.mods import Mods

__all__ = 'PPCalculator',

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
        self.mode = kwargs.get('mode', GameMode.vn_std)
        self.acc = kwargs.get('acc', 100.00)

    @classmethod
    async def get_from_osuapi(cls, map_id: int, dest_path: str) -> bool:
        url = f'https://old.ppy.sh/osu/{map_id}'

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as r:
                if not r or r.status != 200:
                    log(f'Could not find map by id {map_id}!', Ansi.LRED)
                    return False

                content = await r.read()

        async with aiofiles.open(dest_path, 'wb') as f:
            await f.write(content)

        return True

    @classmethod
    async def get_file(cls, map_id: int) -> None:
        filepath = f'.data/osu/{map_id}.osu'
        # check if file exists on disk already
        if not os.path.exists(filepath):
            # not found on disk, try osu!api
            if not await cls.get_from_osuapi(map_id, filepath):
                # failed to find the map
                return

        # map is now on disk, return filepath.
        return filepath

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
        cmd = [f'./oppai-ng/oppai {self.file}']

        if self.mods:  cmd.append(repr(self.mods))
        if self.combo: cmd.append(f'{self.combo}x')
        if self.nmiss: cmd.append(f'{self.nmiss}xM')
        if self.acc:   cmd.append(f'{self.acc:.4f}%')

        if self.mode:
            mode_vn = self.mode.as_vanilla

            if mode_vn not in (0, 1):
                # oppai-ng only supports std & taiko
                # TODO: osu!catch & mania support
                return

            cmd.append(f'-m{mode_vn}')
            if mode_vn == GameMode.vn_taiko:
                cmd.append('-otaiko')

        # XXX: could probably use binary to save a bit
        # of time.. but in reality i should just write
        # some bindings lmao this is so cursed overall
        cmd.append('-ojson')

        # join & run the command
        pipe = asyncio.subprocess.PIPE

        proc = await asyncio.create_subprocess_shell(
            ' '.join(cmd), stdout=pipe, stderr=pipe
        )

        stdout, _ = await proc.communicate() # stderr not needed
        output = orjson.loads(stdout.decode())

        if 'code' not in output or output['code'] != 200:
            log(f"oppai-ng: {output['errstr']}", Ansi.LRED)

        await proc.wait() # wait for exit
        return output['pp'], output['stars']
