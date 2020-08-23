# -*- coding: utf-8 -*-

import asyncio
from typing import Tuple
from os import path

from objects import glob
from console import printlog, Ansi
from constants.mods import mods_readable
from json import loads

__all__ = ('Owoppai',)

class Owoppai:
    __slots__ = ('filename', 'accuracy', 'mods',
                 'combo', 'misses', 'gamemode')

    def __init__(self, **kwargs) -> None:
        self.filename = ''
        self.mods = kwargs.get('mods', 0)
        self.combo = kwargs.get('combo', 0)
        self.misses = kwargs.get('nmiss', 0)
        self.gamemode = kwargs.get('mode', 0)
        self.accuracy = kwargs.get('accuracy', -1.0)

    async def open_map(self, map_id: int) -> None:
        filepath = f'pp/maps/{map_id}.osu'

        if not path.exists(filepath):
            # Do osu!api request for the map.
            async with glob.http.get(f'https://old.ppy.sh/osu/{map_id}') as resp:
                if not resp or resp.status != 200:
                    printlog(f'Could not find map {filepath}!', Ansi.RED) # osu!api request failed.
                    return

                content = await resp.read()

            with open(filepath, 'wb+') as f:
                f.write(content)

        self.filename = filepath

    async def calculate_pp(self) -> Tuple[float, float]:
        # This function can either return a list of
        # PP values, # or just a single PP value.
        if not self.filename:
            printlog('Called calculate_pp() without a map open.', Ansi.RED)
            return

        args = [f'./pp/oppai {self.filename}']
        if self.accuracy >= 0.0:
            args.append(f'{self.accuracy:.4f}%')
        if self.mods >= 0:
            args.append(f'+{mods_readable(self.mods)}')
        if self.combo:
            args.append(f'{self.combo}x')
        if self.misses:
            args.append(f'{self.misses}m')
        if self.gamemode == 1: # taiko support
            args.append('-taiko')

        # Output in json format
        args.append('-ojson')

        proc = await asyncio.create_subprocess_shell(
            ' '.join(args),
            stdout = asyncio.subprocess.PIPE,
            stderr = asyncio.subprocess.PIPE
        )

        stdout, stderr = await proc.communicate()
        output = loads(stdout.decode())

        important = ('code', 'errstr', 'pp', 'stars')
        if any(i not in output for i in important) or output['code'] != 200:
            printlog('Error while calculating PP.', Ansi.RED)
            return

        return output['pp'], output['stars']
