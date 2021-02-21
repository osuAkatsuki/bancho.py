# -*- coding: utf-8 -*-

from enum import IntFlag
from enum import unique

from utils.misc import pymysql_encode
from utils.misc import escape_enum

__all__ = ('Mods',)

@unique
@pymysql_encode(escape_enum)
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
            Mods.FADEIN: 'FI',
            Mods.RANDOM: 'RN',
            Mods.CINEMA: 'CN',
            Mods.TARGET: 'TP',
            Mods.SCOREV2: 'V2',
            Mods.MIRROR: 'MR',

            Mods.KEY1: '1K',
            Mods.KEY2: '2K',
            Mods.KEY3: '3K',
            Mods.KEY4: '4K',
            Mods.KEY5: '5K',
            Mods.KEY6: '6K',
            Mods.KEY7: '7K',
            Mods.KEY8: '8K',
            Mods.KEY9: '9K',
            Mods.KEYCOOP: 'CO'
        }

        mod_str = []

        for m in [_m for _m in Mods if self.value & _m and
                                       _m != Mods.SPEED_CHANGING]:
            mod_str.append(mod_dict[m])
        return ''.join(mod_str)

    def filter_invalid_combos(self, mode_vn: int) -> 'Mods':
        """Remove any invalid mod combinations."""
        if self & (Mods.DOUBLETIME | Mods.NIGHTCORE) and self & Mods.HALFTIME:
            self &= ~Mods.HALFTIME
        if self & Mods.EASY and self & Mods.HARDROCK:
            self &= ~Mods.HARDROCK
        if self & Mods.PERFECT and self & Mods.SUDDENDEATH:
            self &= ~Mods.SUDDENDEATH

        if mode_vn != 0: # osu! specific
            self &= ~(Mods.AUTOPILOT | Mods.SPUNOUT | Mods.TARGET)

        # ctb & taiko have no unique mods

        if mode_vn != 4: # mania specific
            self &= ~(
                Mods.KEY1 | Mods.KEY2 | Mods.KEY3 |
                Mods.KEY4 | Mods.KEY5 | Mods.KEY6 |
                Mods.KEY7 | Mods.KEY8 | Mods.KEY9 |
                Mods.KEYCOOP | Mods.MIRROR |
                Mods.RANDOM | Mods.FADEIN
            )

        # make sure they only have a
        # single keymod enabled.
        keymods_used = self & (
            Mods.KEY1 | Mods.KEY2 | Mods.KEY3 |
            Mods.KEY4 | Mods.KEY5 | Mods.KEY6 |
            Mods.KEY7 | Mods.KEY8 | Mods.KEY9
        )

        # TODO: probably can be faster
        if bin(keymods_used).count('1') > 1:
            # keep only the first
            first_keymod = None
            for mod in Mods:
                if keymods_used & mod:
                    first_keymod = mod
                    break

            # remove all but the first keymod.
            self &= ~(keymods_used & ~first_keymod)

        return self

    @classmethod
    def from_modstr(cls, s: str):
        # from fmt: `HDDTRX`
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
            'CN': cls.CINEMA,
            'AU': cls.AUTOPLAY,
            'TP': cls.TARGET,
            'RX': cls.RELAX,
            'AP': cls.AUTOPILOT,

            '1K': cls.KEY1,
            '2K': cls.KEY2,
            '3K': cls.KEY3,
            '4K': cls.KEY4,
            '5K': cls.KEY5,
            '6K': cls.KEY6,
            '7K': cls.KEY7,
            '8K': cls.KEY8,
            '9K': cls.KEY9,
            'CO': cls.KEYCOOP
        }

        mods = cls.NOMOD

        def get_mod(idx: int) -> str:
            return s[idx:idx + 2].upper()

        for m in map(get_mod, range(0, len(s), 2)):
            if m not in mod_dict:
                continue

            mods |= mod_dict[m]

        return mods

    @classmethod
    def from_np(cls, s: str, mode_vn: int):
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

            '|Cinema|': cls.CINEMA,
            '|Autoplay|': cls.AUTOPLAY,

            '~Target~': cls.TARGET,
            '~Relax~': cls.RELAX,
            '~Autopilot~': cls.AUTOPILOT,

            # perhaps could modify regex
            # to only allow these once,
            # and only at the end of str?
            '|1K|': cls.KEY1,
            '|2K|': cls.KEY2,
            '|3K|': cls.KEY3,
            '|4K|': cls.KEY4,
            '|5K|': cls.KEY5,
            '|6K|': cls.KEY6,
            '|7K|': cls.KEY7,
            '|8K|': cls.KEY8,
            '|9K|': cls.KEY9,

            # XXX: kinda mood that there's no way
            # to tell K1-K4 co-op from /np, but
            # scores won't submit or anything so
            # it's not ultimately a problem.
            '|10K|': cls.KEY5 | cls.KEYCOOP,
            '|12K|': cls.KEY6 | cls.KEYCOOP,
            '|14K|': cls.KEY7 | cls.KEYCOOP,
            '|16K|': cls.KEY8 | cls.KEYCOOP,
            '|18K|': cls.KEY9 | cls.KEYCOOP
        }

        mods = cls.NOMOD

        for mod in s.split(' '):
            if mod not in mod_dict:
                continue

            mods |= mod_dict[mod]

        # NOTE: for fetching from /np, we automatically
        # call cls.filter_invalid_combos as we assume
        # the input string is from user input.
        return mods.filter_invalid_combos(mode_vn)
