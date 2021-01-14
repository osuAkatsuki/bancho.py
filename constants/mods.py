# -*- coding: utf-8 -*-

from enum import IntFlag, unique

__all__ = ('Mods',)

@unique
class Mods(IntFlag):
    NOMOD       = 0
    NOFAIL      = 1 << 0
    EASY        = 1 << 1
    TOUCHSCREEN = 1 << 2 # old: 'NOVIDEO'
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
    AUTOPILOT   = 1 << 13
    PERFECT     = 1 << 14
    KEY4        = 1 << 15
    KEY5        = 1 << 16
    KEY6        = 1 << 17
    KEY7        = 1 << 18
    KEY8        = 1 << 19
    FADEIN      = 1 << 20
    RANDOM      = 1 << 21
    CINEMA      = 1 << 22
    TARGET      = 1 << 23
    KEY9        = 1 << 24
    KEYCOOP     = 1 << 25
    KEY1        = 1 << 26
    KEY3        = 1 << 27
    KEY2        = 1 << 28
    SCOREV2     = 1 << 29
    MIRROR      = 1 << 30

    # XXX: needs some modification to work..
    #KEY_MOD = KEY1 | KEY2 | KEY3 | KEY4 | KEY5 | KEY6 | KEY7 | KEY8 | KEY9 | KEYCOOP
    #FREE_MOD_ALLOWED = NOFAIL | EASY | HIDDEN | HARDROCK | \
    #                 SUDDENDEATH | FLASHLIGHT | FADEIN | \
    #                 RELAX | AUTOPILOT | SPUNOUT | KEY_MOD
    #SCORE_INCREASE_MODS = HIDDEN | HARDROCK | DOUBLETIME | FLASHLIGHT | FADEIN
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
            Mods.AUTOPILOT: 'AP',
            Mods.PERFECT: 'PF',
            Mods.KEY4: 'K4',
            Mods.KEY5: 'K5',
            Mods.KEY6: 'K6',
            Mods.KEY7: 'K7',
            Mods.KEY8: 'K8',
            Mods.FADEIN: 'FI',
            Mods.RANDOM: 'RN',
            Mods.CINEMA: 'CN',
            Mods.TARGET: 'TP',
            Mods.KEY9: 'K9',
            Mods.KEYCOOP: 'CO',
            Mods.KEY1: 'K1',
            Mods.KEY3: 'K3',
            Mods.KEY2: 'K2',
            Mods.SCOREV2: 'V2',
            Mods.MIRROR: 'MR'
        }

        mod_str = []

        for m in (_m for _m in Mods if self.value & _m
                                    and _m != Mods.SPEED_CHANGING):
            mod_str.append(mod_dict[m])
        return ''.join(mod_str)

    @staticmethod
    def filter_invalid_combos(m: 'Mods') -> 'Mods':
        """Remove any invalid mod combinations from and return `m`."""
        if m & (Mods.DOUBLETIME | Mods.NIGHTCORE) and m & Mods.HALFTIME:
            m &= ~Mods.HALFTIME
        if m & Mods.EASY and m & Mods.HARDROCK:
            m &= ~Mods.HARDROCK
        if m & Mods.RELAX and m & Mods.AUTOPILOT:
            m &= ~Mods.AUTOPILOT
        if m & Mods.PERFECT and m & Mods.SUDDENDEATH:
            m &= ~Mods.SUDDENDEATH

        return m

    @classmethod
    def from_str(cls, s: str):
        # from fmt: `HDDTRX`
        # TODO: check for invalid mod combos
        mod_dict = {
            'EZ': cls.EASY,
            'NF': cls.NOFAIL,
            'HD': cls.HIDDEN,
            'PF': cls.PERFECT,
            'SD': cls.SUDDENDEATH,
            'HR': cls.HARDROCK,
            'NC': cls.NIGHTCORE,
            'DT': cls.DOUBLETIME,
            'HT': cls.HALFTIME,
            'FL': cls.FLASHLIGHT,
            'SO': cls.SPUNOUT,
            'RX': cls.RELAX,
            'AP': cls.AUTOPILOT
        }

        mods = cls.NOMOD

        for m in map(lambda i: s[i:i+2].upper(), range(0, len(s), 2)):
            if m not in mod_dict:
                continue

            mods |= mod_dict[m]

        return cls.filter_invalid_combos(mods)

    @classmethod
    def from_np(cls, s: str):
        # TODO: check for invalid mod combos
        # from fmt: `-DiffDown +DiffUp ~Special~`
        mod_dict = {
            '-Easy': cls.EASY,
            '-NoFail': cls.NOFAIL,
            '+Hidden': cls.HIDDEN,
            '+Perfect': cls.PERFECT,
            '+SuddenDeath': cls.SUDDENDEATH,
            '+HardRock': cls.HARDROCK,
            '+Nightcore': cls.NIGHTCORE,
            '+DoubleTime': cls.DOUBLETIME,
            '-HalfTime': cls.HALFTIME,
            '+Flashlight': cls.FLASHLIGHT,
            '-SpunOut': cls.SPUNOUT,
            '~Relax~': cls.RELAX,
            '~Autopilot~': cls.AUTOPILOT
        }

        mods = cls.NOMOD

        for mod in s.split(' '):
            # a bit unsafe.. perhaps defaultdict?
            mods |= mod_dict[mod]

        return cls.filter_invalid_combos(mods)
