# -*- coding: utf-8 -*-

from typing import Optional, Tuple, Any
import os

import aiofiles

from oppai import *
from objects import glob
from console import plog, Ansi

__all__ = 'Owoppai',

class Owoppai:
    __slots__ = ('map_id', 'mods', 'combo',
                 'nmiss', 'mode', 'acc', 'ez')

    def __init__(self, map_id: int, **kwargs) -> None:
        self.map_id = map_id

        self.mods: int = kwargs.get('mods', 0)
        self.combo: int = kwargs.get('combo', 0)
        self.nmiss: int = kwargs.get('nmiss', 0)
        self.mode: int = kwargs.get('mode', 0)
        self.acc: float = kwargs.get('acc', -1.0)

        # Instance of oppai-ng.
        # Will stay as None until a valid
        # beatmap file has been found on disk.
        self.ez: Optional[Any] = None

    async def __aenter__(self):
        filename = f'pp/maps/{self.map_id}.osu'

        # Get file from either disk, or the osu!api if not found.
        if os.path.exists(filename) or await self.get_from_osuapi(filename):
            self.ez = ezpp_new()
            ezpp(self.ez, filename)

            # Auto recalc when changing any param.
            ezpp_set_autocalc(self.ez, 1)

            # Update state from any kwargs passed in.
            if self.mods != 0:
                ezpp_set_mods(self.ez, self.mods)

            if self.combo != 0:
                ezpp_set_combo(self.ez, self.combo)

            if self.nmiss != 0:
                ezpp_set_nmiss(self.ez, self.nmiss)

            if self.acc != -1:
                ezpp_set_accuracy_percent(self.ez, self.acc)

            if self.mode == 1: # taiko support
                ezpp_set_mode(self.ez, 1)
                ezpp_set_mode_override(self.ez, 1)

        return self

    async def __aexit__(self, exc_type, exc, tb):
        ezpp_free(self.ez)

    """ Customization"""
    def set_mods(self, mods: int) -> None:
        ezpp_set_mods(self.ez, mods)

    def set_combo(self, combo: int) -> None:
        ezpp_set_combo(self.ez, combo)

    def set_nmiss(self, nmiss: int) -> None:
        ezpp_set_nmiss(self.ez, nmiss)

    def set_mode(self, mode: int) -> None:
        if mode not in (0, 1):
            return

        ezpp_set_mods(self.ez, mode)
        ezpp_set_mode_override(self.ez, mode == 1)

    def set_acc(self, acc: float) -> None:
        ezpp_set_accuracy_percent(self.ez, acc)

    """ PP """
    @property
    def pp(self) -> float:
        if self.ez:
            if self.mode == 0 and self.mods & 128:
                # Relax osu!std - no speed pp.
                return ezpp_aim_pp(self.ez) + ezpp_acc_pp(self.ez)
            else: # For any other mode, return normal pp.
                return ezpp_pp(self.ez)
        else: # No map found
            return 0.0

    @property
    def aim_pp(self) -> float:
        return ezpp_aim_pp(self.ez) if self.ez else 0.0

    @property
    def speed_pp(self) -> float:
        return ezpp_speed_pp(self.ez) if self.ez else 0.0

    @property
    def acc_pp(self) -> float:
        return ezpp_acc_pp(self.ez) if self.ez else 0.0

    """ Stars """
    @property
    def stars(self) -> float:
        return ezpp_stars(self.ez) if self.ez else 0.0

    @property
    def aim_stars(self) -> float:
        return ezpp_aim_stars(self.ez) if self.ez else 0.0

    @property
    def speed_stars(self) -> float:
        return ezpp_speed_stars(self.ez) if self.ez else 0.0

    async def get_from_osuapi(self, filename: str) -> bool:
        # Get the map's .osu file from the osu!api.
        async with glob.http.get(f'https://old.ppy.sh/osu/{self.map_id}') as resp:
            if not resp or resp.status != 200:
                await plog(f'Could not find map {filename}!', Ansi.LIGHT_RED) # osu!api request failed.
                return False

            content = await resp.read()

        async with aiofiles.open(filename, 'wb+') as f:
            await f.write(content)

        return True
