# -*- coding: utf-8 -*-

from typing import Final, Union
from enum import IntEnum, unique

__all__ = ('Mods',)

@unique
class Mods(IntEnum):
    NOMOD:          Final[int] = 0
    NOFAIL:         Final[int] = 1 << 0
    EASY:           Final[int] = 1 << 1
    TOUCHSCREEN:    Final[int] = 1 << 2
    HIDDEN:         Final[int] = 1 << 3
    HARDROCK:       Final[int] = 1 << 4
    SUDDENDEATH:    Final[int] = 1 << 5
    DOUBLETIME:     Final[int] = 1 << 6
    RELAX:          Final[int] = 1 << 7
    HALFTIME:       Final[int] = 1 << 8
    NIGHTCORE:      Final[int] = 1 << 9
    FLASHLIGHT:     Final[int] = 1 << 10
    AUTOPLAY:       Final[int] = 1 << 11
    SPUNOUT:        Final[int] = 1 << 12
    RELAX2:         Final[int] = 1 << 13
    PERFECT:        Final[int] = 1 << 14
    KEY4:           Final[int] = 1 << 15
    KEY5:           Final[int] = 1 << 16
    KEY6:           Final[int] = 1 << 17
    KEY7:           Final[int] = 1 << 18
    KEY8:           Final[int] = 1 << 19
    KEYMOD:         Final[int] = 1 << 20
    FADEIN:         Final[int] = 1 << 21
    RANDOM:         Final[int] = 1 << 22
    LASTMOD:        Final[int] = 1 << 23
    KEY9:           Final[int] = 1 << 24
    KEY10:          Final[int] = 1 << 25
    KEY1:           Final[int] = 1 << 26
    KEY3:           Final[int] = 1 << 27
    KEY2:           Final[int] = 1 << 28
    SCOREV2:        Final[int] = 1 << 29

    SPEED_CHANGING: Final[int] = DOUBLETIME | NIGHTCORE | HALFTIME

def mods_readable(m: Union[Mods, int]) -> str:
    if not m: return ''

    r: List[str] = []
    if m & Mods.NOFAIL:       r.append('NF')
    if m & Mods.EASY:         r.append('EZ')
    if m & Mods.TOUCHSCREEN:  r.append('TD')
    if m & Mods.HIDDEN:       r.append('HD')
    if m & Mods.HARDROCK:     r.append('HR')
    if m & Mods.NIGHTCORE:    r.append('NC')
    elif m & Mods.DOUBLETIME: r.append('DT')
    if m & Mods.RELAX:        r.append('RX')
    if m & Mods.HALFTIME:     r.append('HT')
    if m & Mods.FLASHLIGHT:   r.append('FL')
    if m & Mods.SPUNOUT:      r.append('SO')
    if m & Mods.SCOREV2:      r.append('V2')
    return ''.join(r)
