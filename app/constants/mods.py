from __future__ import annotations

import functools
from enum import IntFlag
from enum import unique

from app.utils import escape_enum
from app.utils import pymysql_encode

__all__ = ("Mods",)

# NOTE: the order of some of these = stupid


@unique
@pymysql_encode(escape_enum)
class Mods(IntFlag):
    NOMOD = 0
    NOFAIL = 1 << 0
    EASY = 1 << 1
    TOUCHSCREEN = 1 << 2  # old: 'NOVIDEO'
    HIDDEN = 1 << 3
    HARDROCK = 1 << 4
    SUDDENDEATH = 1 << 5
    DOUBLETIME = 1 << 6
    RELAX = 1 << 7
    HALFTIME = 1 << 8
    NIGHTCORE = 1 << 9
    FLASHLIGHT = 1 << 10
    AUTOPLAY = 1 << 11
    SPUNOUT = 1 << 12
    AUTOPILOT = 1 << 13
    PERFECT = 1 << 14
    KEY4 = 1 << 15
    KEY5 = 1 << 16
    KEY6 = 1 << 17
    KEY7 = 1 << 18
    KEY8 = 1 << 19
    FADEIN = 1 << 20
    RANDOM = 1 << 21
    CINEMA = 1 << 22
    TARGET = 1 << 23
    KEY9 = 1 << 24
    KEYCOOP = 1 << 25
    KEY1 = 1 << 26
    KEY3 = 1 << 27
    KEY2 = 1 << 28
    SCOREV2 = 1 << 29
    MIRROR = 1 << 30

    @functools.cache
    def __repr__(self) -> str:
        if self.value == Mods.NOMOD:
            return "NM"

        mod_str = []
        _dict = mod2modstr_dict  # global

        for mod in Mods:
            if self.value & mod:
                mod_str.append(_dict[mod])

        return "".join(mod_str)

    def filter_invalid_combos(self, mode_vn: int) -> Mods:
        """Remove any invalid mod combinations."""

        # 1. mode-inspecific mod conflictions
        _dtnc = self & (Mods.DOUBLETIME | Mods.NIGHTCORE)
        if _dtnc == (Mods.DOUBLETIME | Mods.NIGHTCORE):
            self &= ~Mods.DOUBLETIME  # DTNC
        elif _dtnc and self & Mods.HALFTIME:
            self &= ~Mods.HALFTIME  # (DT|NC)HT

        if self & Mods.EASY and self & Mods.HARDROCK:
            self &= ~Mods.HARDROCK  # EZHR

        if self & (Mods.NOFAIL | Mods.RELAX | Mods.AUTOPILOT):
            if self & Mods.SUDDENDEATH:
                self &= ~Mods.SUDDENDEATH  # (NF|RX|AP)SD
            if self & Mods.PERFECT:
                self &= ~Mods.PERFECT  # (NF|RX|AP)PF

        if self & (Mods.RELAX | Mods.AUTOPILOT):
            if self & Mods.NOFAIL:
                self &= ~Mods.NOFAIL  # (RX|AP)NF

        if self & Mods.PERFECT and self & Mods.SUDDENDEATH:
            self &= ~Mods.SUDDENDEATH  # PFSD

        # 2. remove mode-unique mods from incorrect gamemodes
        if mode_vn != 0:  # osu! specific
            self &= ~OSU_SPECIFIC_MODS

        # ctb & taiko have no unique mods

        if mode_vn != 3:  # mania specific
            self &= ~MANIA_SPECIFIC_MODS

        # 3. mode-specific mod conflictions
        if mode_vn == 0:
            if self & Mods.AUTOPILOT:
                if self & (Mods.SPUNOUT | Mods.RELAX):
                    self &= ~Mods.AUTOPILOT  # (SO|RX)AP

        if mode_vn == 3:
            self &= ~Mods.RELAX  # rx is std/taiko/ctb common
            if self & Mods.HIDDEN and self & Mods.FADEIN:
                self &= ~Mods.FADEIN  # HDFI

        # 4 remove multiple keymods
        # TODO: do this better
        keymods_used = self & KEY_MODS

        if bin(keymods_used).count("1") > 1:
            # keep only the first
            first_keymod = None
            for mod in KEY_MODS:
                if keymods_used & mod:
                    first_keymod = mod
                    break

            # remove all but the first keymod.
            self &= ~(keymods_used & ~first_keymod)

        return self

    @classmethod
    @functools.lru_cache(maxsize=64)
    def from_modstr(cls, s: str) -> Mods:
        # from fmt: `HDDTRX`
        mods = cls.NOMOD
        _dict = modstr2mod_dict  # global

        # split into 2 character chunks
        mod_strs = [s[idx : idx + 2].upper() for idx in range(0, len(s), 2)]

        # find matching mods
        for mod in mod_strs:
            if mod not in _dict:
                continue

            mods |= _dict[mod]

        return mods

    @classmethod
    @functools.lru_cache(maxsize=64)
    def from_np(cls, s: str, mode_vn: int) -> Mods:
        mods = cls.NOMOD
        _dict = npstr2mod_dict  # global

        # TODO: dis
        for mod in s.split(" "):
            if mod not in _dict:
                continue

            mods |= _dict[mod]

        # NOTE: for fetching from /np, we automatically
        # call cls.filter_invalid_combos as we assume
        # the input string is from user input.
        return mods.filter_invalid_combos(mode_vn)


modstr2mod_dict = {
    "NF": Mods.NOFAIL,
    "EZ": Mods.EASY,
    "TD": Mods.TOUCHSCREEN,
    "HD": Mods.HIDDEN,
    "HR": Mods.HARDROCK,
    "SD": Mods.SUDDENDEATH,
    "DT": Mods.DOUBLETIME,
    "RX": Mods.RELAX,
    "HT": Mods.HALFTIME,
    "NC": Mods.NIGHTCORE,
    "FL": Mods.FLASHLIGHT,
    "AU": Mods.AUTOPLAY,
    "SO": Mods.SPUNOUT,
    "AP": Mods.AUTOPILOT,
    "PF": Mods.PERFECT,
    "FI": Mods.FADEIN,
    "RN": Mods.RANDOM,
    "CN": Mods.CINEMA,
    "TP": Mods.TARGET,
    "V2": Mods.SCOREV2,
    "MR": Mods.MIRROR,
    "1K": Mods.KEY1,
    "2K": Mods.KEY2,
    "3K": Mods.KEY3,
    "4K": Mods.KEY4,
    "5K": Mods.KEY5,
    "6K": Mods.KEY6,
    "7K": Mods.KEY7,
    "8K": Mods.KEY8,
    "9K": Mods.KEY9,
    "CO": Mods.KEYCOOP,
}

npstr2mod_dict = {
    "-NoFail": Mods.NOFAIL,
    "-Easy": Mods.EASY,
    "+Hidden": Mods.HIDDEN,
    "+HardRock": Mods.HARDROCK,
    "+SuddenDeath": Mods.SUDDENDEATH,
    "+DoubleTime": Mods.DOUBLETIME,
    "~Relax~": Mods.RELAX,
    "-HalfTime": Mods.HALFTIME,
    "+Nightcore": Mods.NIGHTCORE,
    "+Flashlight": Mods.FLASHLIGHT,
    "|Autoplay|": Mods.AUTOPLAY,
    "-SpunOut": Mods.SPUNOUT,
    "~Autopilot~": Mods.AUTOPILOT,
    "+Perfect": Mods.PERFECT,
    "|Cinema|": Mods.CINEMA,
    "~Target~": Mods.TARGET,
    # perhaps could modify regex
    # to only allow these once,
    # and only at the end of str?
    "|1K|": Mods.KEY1,
    "|2K|": Mods.KEY2,
    "|3K|": Mods.KEY3,
    "|4K|": Mods.KEY4,
    "|5K|": Mods.KEY5,
    "|6K|": Mods.KEY6,
    "|7K|": Mods.KEY7,
    "|8K|": Mods.KEY8,
    "|9K|": Mods.KEY9,
    # XXX: kinda mood that there's no way
    # to tell K1-K4 co-op from /np, but
    # scores won't submit or anything, so
    # it's not ultimately a problem.
    "|10K|": Mods.KEY5 | Mods.KEYCOOP,
    "|12K|": Mods.KEY6 | Mods.KEYCOOP,
    "|14K|": Mods.KEY7 | Mods.KEYCOOP,
    "|16K|": Mods.KEY8 | Mods.KEYCOOP,
    "|18K|": Mods.KEY9 | Mods.KEYCOOP,
}

mod2modstr_dict = {
    Mods.NOFAIL: "NF",
    Mods.EASY: "EZ",
    Mods.TOUCHSCREEN: "TD",
    Mods.HIDDEN: "HD",
    Mods.HARDROCK: "HR",
    Mods.SUDDENDEATH: "SD",
    Mods.DOUBLETIME: "DT",
    Mods.RELAX: "RX",
    Mods.HALFTIME: "HT",
    Mods.NIGHTCORE: "NC",
    Mods.FLASHLIGHT: "FL",
    Mods.AUTOPLAY: "AU",
    Mods.SPUNOUT: "SO",
    Mods.AUTOPILOT: "AP",
    Mods.PERFECT: "PF",
    Mods.FADEIN: "FI",
    Mods.RANDOM: "RN",
    Mods.CINEMA: "CN",
    Mods.TARGET: "TP",
    Mods.SCOREV2: "V2",
    Mods.MIRROR: "MR",
    Mods.KEY1: "1K",
    Mods.KEY2: "2K",
    Mods.KEY3: "3K",
    Mods.KEY4: "4K",
    Mods.KEY5: "5K",
    Mods.KEY6: "6K",
    Mods.KEY7: "7K",
    Mods.KEY8: "8K",
    Mods.KEY9: "9K",
    Mods.KEYCOOP: "CO",
}

KEY_MODS = (
    Mods.KEY1
    | Mods.KEY2
    | Mods.KEY3
    | Mods.KEY4
    | Mods.KEY5
    | Mods.KEY6
    | Mods.KEY7
    | Mods.KEY8
    | Mods.KEY9
)

# FREE_MOD_ALLOWED = (
#    Mods.NOFAIL | Mods.EASY | Mods.HIDDEN | Mods.HARDROCK |
#    Mods.SUDDENDEATH | Mods.FLASHLIGHT | Mods.FADEIN |
#    Mods.RELAX | Mods.AUTOPILOT | Mods.SPUNOUT | KEY_MODS
# )

SCORE_INCREASE_MODS = (
    Mods.HIDDEN | Mods.HARDROCK | Mods.FADEIN | Mods.DOUBLETIME | Mods.FLASHLIGHT
)

SPEED_CHANGING_MODS = Mods.DOUBLETIME | Mods.NIGHTCORE | Mods.HALFTIME

OSU_SPECIFIC_MODS = Mods.AUTOPILOT | Mods.SPUNOUT | Mods.TARGET
# taiko & catch have no specific mods
MANIA_SPECIFIC_MODS = Mods.MIRROR | Mods.RANDOM | Mods.FADEIN | KEY_MODS
