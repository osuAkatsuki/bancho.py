# -*- coding: utf-8 -*-

from typing import Tuple
from os import path
from subprocess import run, PIPE
from constants.mods import mods_readable
from json import loads
from requests import get as req_get

__all__ = ('Owoppai',)

class Owoppai:
    __slots__ = ('filename', 'accuracy', 'mods',
                 'combo', 'misses', 'gamemode')

    def __init__(self, **kwargs) -> None:
        if 'map_id' in kwargs:
            self.open_map(kwargs.get('map_id'))

        self.mods = kwargs.get('mods', 0)
        self.combo = kwargs.get('combo', 0)
        self.misses = kwargs.get('nmiss', 0)
        self.gamemode = kwargs.get('mode', 0)
        self.accuracy = kwargs.get('accuracy', -1.0)

    def open_map(self, map_id: int) -> None:
        filepath = f'pp/maps/{map_id}.osu'
        if not path.exists(filepath):
            # Do osu!api request for the map.
            if not (r := req_get(f'https://old.ppy.sh/osu/{map_id}')):
                raise Exception(f'Could not find map {filepath}!')

            with open(filepath, 'wb+') as f:
                f.write(r.content)

        self.filename = filepath

    def calculate_pp(self) -> Tuple[float, float]:
        # This function can either return a list of
        # PP values, # or just a single PP value.
        if not self.filename: raise Exception(
            'Must open a map prior to calling calculate_pp()')

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

        process = run(
            ' '.join(args),
            shell = True, stdout = PIPE, stderr = PIPE)

        output = loads(process.stdout.decode('utf-8', errors='ignore'))

        important = ('code', 'errstr', 'pp', 'stars')
        if any(i not in output for i in important) or output['code'] != 200:
            raise Exception('Error while calculating PP')

        return output['pp'], output['stars']
