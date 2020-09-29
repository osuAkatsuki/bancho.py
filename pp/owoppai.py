# -*- coding: utf-8 -*-

import asyncio
import aiofiles
import aiohttp
import orjson
import os
import time

from constants.gamemodes import GameMode
from constants.mods import Mods

from console import plog, Ansi

__all__ = 'Owoppai',

mod_strings = {
    Mods.NOFAIL: 'NF',
    Mods.EASY: 'EZ',
    Mods.TOUCHSCREEN: 'TD',
    Mods.HIDDEN: 'HD',
    Mods.HARDROCK: 'HR',
    Mods.SUDDENDEATH: 'SD',
    Mods.DOUBLETIME: 'DT',
    Mods.RELAX: 'RX',
    Mods.HALFTIME: 'HT',
    Mods.NIGHTCORE: 'NC',
    Mods.FLASHLIGHT: 'FL',
    Mods.AUTOPLAY: 'AU',
    Mods.SPUNOUT: 'SO',
    Mods.RELAX2: 'AP',
    Mods.PERFECT: 'PF',
    Mods.KEY4: 'K4',
    Mods.KEY5: 'K5',
    Mods.KEY6: 'K6',
    Mods.KEY7: 'K7',
    Mods.KEY8: 'K8',
    Mods.KEYMOD: '??',
    Mods.FADEIN: 'FI',
    Mods.RANDOM: 'RD', # unsure
    Mods.LASTMOD: 'LM', # unsure
    Mods.KEY9: 'K9',
    Mods.KEY10: 'K10', # unsure
    Mods.KEY1: 'K1',
    Mods.KEY3: 'K3',
    Mods.KEY2: 'K2',
    Mods.SCOREV2: 'V2'
}

class Owoppai:
    __slots__ = ('map_id', 'filename', 'mods',
                 'combo', 'nmiss', 'mode', 'acc',
                 'output')

    def __init__(self, map_id: int, **kwargs) -> None:
        self.map_id = map_id

        self.filename = f'pp/maps/{self.map_id}.osu'

        # TODO: perhaps make an autocalc mode w/ properties?
        self.mods: Mods = kwargs.pop('mods', Mods.NOMOD)
        self.combo: int = kwargs.pop('combo', 0)
        self.nmiss: int = kwargs.pop('nmiss', 0)
        self.mode: GameMode = kwargs.pop('mode', GameMode.vn_std)
        self.acc: float = kwargs.pop('acc', 100.00)

        # json output from oppai-ng
        self.output = {}

    async def __aenter__(self):
        if not self.filename \
        or not os.path.exists(self.filename):
            await plog(f'Could not find {self.filename}.', Ansi.LIGHT_RED)
            return

        await self.calc()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return

    async def calc(self) -> None:
        st = time.time()
        # perform the calculations using current state
        args = [f'./oppai-ng/oppai {self.filename}']

        if self.mods > Mods.NOMOD:
            args.append(repr(self.mods))
        if self.combo:
            args.append(f'{self.combo}x')
        if self.nmiss:
            args.append(f'{self.nmiss}xM')
        if self.mode:
            args.append(f'-m{int(self.mode)}')
            if self.mode == GameMode.vn_taiko:
                args.append('-otaiko')
        if self.acc:
            args.append(f'{self.acc:.4f}%')

        args.append('-ojson')

        proc = await asyncio.create_subprocess_shell(
            ' '.join(args),
            stdout = asyncio.subprocess.PIPE,
            stderr = asyncio.subprocess.PIPE
        )

        stdout, stderr = await proc.communicate()
        output = orjson.loads(stdout.decode())
        self.output = output

        important = ('code', 'errstr', 'pp', 'stars')
        if any(i not in output for i in important) or output['code'] != 200:
            await plog(f"oppai-ng error: {output['errstr']}", Ansi.LIGHT_RED)

        await proc.wait()
        print(f'{(time.time()-st)*1000}ms')

    @classmethod
    async def from_md5(cls, md5: str, **kwargs):
        # TODO: coming soon :P
        raise NotImplementedError()

    @classmethod
    async def get_osuapi(cls, map_id: int, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://old.ppy.sh/osu/{map_id}') as r:
                if not r or r.status != 200:
                    await plog(f'Could not find map by id {map_id}!', Ansi.LIGHT_RED)
                    return

                content = await r.read()

        filename = f'pp/maps/{map_id}.osu'

        async with aiofiles.open(filename, 'wb') as f:
            await f.write(content)

        return cls(map_id = map_id, **kwargs)

    def _output(self, key: str, default):
        if key not in self.output:
            return default

        return self.output[key]

    @property
    def pp(self) -> float:
        return self._output('pp', 0.0)

    @property
    def acc_pp(self) -> float:
        return self._output('acc_pp', 0.0)

    @property
    def aim_pp(self) -> float:
        return self._output('aim_pp', 0.0)

    @property
    def speed_pp(self) -> float:
        return self._output('speed_pp', 0.0)

    @property
    def stars(self) -> float:
        return self._output('stars', 0.0)

    @property
    def acc_stars(self) -> float:
        return self._output('acc_stars', 0.0)

    @property
    def aim_stars(self) -> float:
        return self._output('aim_stars', 0.0)

    @property
    def speed_stars(self) -> float:
        return self._output('speed_stars', 0.0)
