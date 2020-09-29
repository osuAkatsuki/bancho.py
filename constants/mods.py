# -*- coding: utf-8 -*-

from typing import Union, List
from enum import IntFlag, unique

__all__ = 'Mods',

@unique
class Mods(IntFlag):
    NOMOD       = 0
    NOFAIL      = 1 << 0
    EASY        = 1 << 1
    TOUCHSCREEN = 1 << 2
    HIDDEN      = 1 << 3
    HARDROCK    = 1 << 4
    SUDDENDEATH = 1 << 5
    DOUBLETIME  = 1 << 6
    RELAX       = 1 << 7
    HALFTIME    = 1 << 8
    NIGHTCORE   = 1 << 9
    FLASHLIGHT  = 1 << 10
    AUTOPLAY    = 1 << 11
    SPUNOUT     = 1 << 12
    RELAX2      = 1 << 13
    PERFECT     = 1 << 14
    KEY4        = 1 << 15
    KEY5        = 1 << 16
    KEY6        = 1 << 17
    KEY7        = 1 << 18
    KEY8        = 1 << 19
    KEYMOD      = 1 << 20
    FADEIN      = 1 << 21
    RANDOM      = 1 << 22
    LASTMOD     = 1 << 23
    KEY9        = 1 << 24
    KEY10       = 1 << 25
    KEY1        = 1 << 26
    KEY3        = 1 << 27
    KEY2        = 1 << 28
    SCOREV2     = 1 << 29

    SPEED_CHANGING = DOUBLETIME | NIGHTCORE | HALFTIME

    def __repr__(self) -> str:
        if self.value == Mods.NOMOD:
            return ''

        mod_dict = {
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
            Mods.FADEIN: 'FI', # TODO: fix these
            Mods.RANDOM: '__', # unsure
            Mods.LASTMOD: '__', # unsure
            Mods.KEY9: 'K9',
            Mods.KEY10: '__', # unsure
            Mods.KEY1: 'K1',
            Mods.KEY3: 'K3',
            Mods.KEY2: 'K2',
            Mods.SCOREV2: 'V2'
        }

        mod_str = []

        for m in (_m for _m in Mods if self.value & _m
                                    and _m != Mods.SPEED_CHANGING):
            mod_str.append(mod_dict[m])
        return f"+{''.join(mod_str)}"

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
