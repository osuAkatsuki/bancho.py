from __future__ import annotations

import functools

__all__ = ("Mods",)

class Mods:
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

    @classmethod
    def to_string(cls, mods: int) -> str:
        if mods == cls.NOMOD:
            return "NM"

        mod_str = []
        mod_dict = {
            cls.NOFAIL: "NF",
            cls.EASY: "EZ",
            cls.TOUCHSCREEN: "TD",
            cls.HIDDEN: "HD",
            cls.HARDROCK: "HR",
            cls.SUDDENDEATH: "SD",
            cls.DOUBLETIME: "DT",
            cls.RELAX: "RX",
            cls.HALFTIME: "HT",
            cls.NIGHTCORE: "NC",
            cls.FLASHLIGHT: "FL",
            cls.AUTOPLAY: "AU",
            cls.SPUNOUT: "SO",
            cls.AUTOPILOT: "AP",
            cls.PERFECT: "PF",
            cls.FADEIN: "FI",
            cls.RANDOM: "RN",
            cls.CINEMA: "CN",
            cls.TARGET: "TP",
            cls.SCOREV2: "V2",
            cls.MIRROR: "MR",
            cls.KEY1: "1K",
            cls.KEY2: "2K",
            cls.KEY3: "3K",
            cls.KEY4: "4K",
            cls.KEY5: "5K",
            cls.KEY6: "6K",
            cls.KEY7: "7K",
            cls.KEY8: "8K",
            cls.KEY9: "9K",
            cls.KEYCOOP: "CO",
        }
        for mod, string in mod_dict.items():
            if mods & mod:
                mod_str.append(string)

        return "".join(mod_str)

    @classmethod
    def filter_invalid_combos(cls, mods: int, mode_vn: int) -> int:
        if (mods & cls.DOUBLETIME) and (mods & cls.NIGHTCORE):
            mods &= ~cls.DOUBLETIME  # (NC)DT
        if (mods & (cls.DOUBLETIME | cls.NIGHTCORE)) and (mods & cls.HALFTIME):
            mods &= ~cls.HALFTIME  # (DT|NC)HT

        if (mods & cls.EASY) and (mods & cls.HARDROCK):
            mods &= ~cls.HARDROCK  # (EZ)HR

        if (mods & (cls.NOFAIL | cls.RELAX | cls.AUTOPILOT)) and (mods & cls.SUDDENDEATH):
            mods &= ~cls.SUDDENDEATH  # (NF|RX|AP)SD
        if (mods & (cls.NOFAIL | cls.RELAX | cls.AUTOPILOT)) and (mods & cls.PERFECT):
            mods &= ~cls.PERFECT  # (NF|RX|AP)PF

        if (mods & (cls.RELAX | cls.AUTOPILOT)) and (mods & cls.NOFAIL):
            mods &= ~cls.NOFAIL  # (RX|AP)NF

        if (mods & cls.PERFECT) and (mods & cls.SUDDENDEATH):
            mods &= ~cls.SUDDENDEATH  # (PF)SD

        if mode_vn != 0:
            mods &= ~OSU_SPECIFIC_MODS

        if mode_vn != 3:
            mods &= ~MANIA_SPECIFIC_MODS

        if mode_vn == 0:
            if (mods & cls.AUTOPILOT) and (mods & (cls.SPUNOUT | cls.RELAX)):
                mods &= ~cls.AUTOPILOT  # (SO|RX)AP

        if mode_vn == 3:
            mods &= ~cls.RELAX 
            if (mods & cls.HIDDEN) and (mods & cls.FADEIN):
                mods &= ~cls.FADEIN  # (HD)FI

        keymods_used = mods & KEY_MODS

        if keymods_used & (keymods_used - 1):
            # remove all but the lowest keymod
            mods &= keymods_used & -keymods_used

        return mods

    @classmethod
    def from_modstr(s: str) -> int:
        mods = 0
        mod_dict = {
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

        # split into 2 character chunks
        mod_strs = [s[idx : idx + 2].upper() for idx in range(0, len(s), 2)]

        # find matching mods
        for m in mod_strs:
            if m in mod_dict:
                mods |= mod_dict[m]

        return mods
    
    @classmethod
    def from_np(cls, s: str, mode_vn: int) -> int:
        mods = 0
        mod_strs = s.split(" ")
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
            # scores won't submit or anything so
            # it's not ultimately a problem.
            "|10K|": Mods.KEY5 | Mods.KEYCOOP,
            "|12K|": Mods.KEY6 | Mods.KEYCOOP,
            "|14K|": Mods.KEY7 | Mods.KEYCOOP,
            "|16K|": Mods.KEY8 | Mods.KEYCOOP,
            "|18K|": Mods.KEY9 | Mods.KEYCOOP,
        }

        for mod_str in mod_strs:
            if mod_str in npstr2mod_dict:
                mods |= npstr2mod_dict[mod_str]

        return cls.filter_invalid_combos(mods, mode_vn)
    

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

SPEED_CHANGING_MODS = Mods.DOUBLETIME | Mods.NIGHTCORE | Mods.HALFTIME
