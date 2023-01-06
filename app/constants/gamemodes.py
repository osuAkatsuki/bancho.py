from __future__ import annotations

import functools
from enum import IntEnum
from enum import unique

from app.constants.mods import Mods
from app.utils import escape_enum
from app.utils import pymysql_encode

__all__ = ("GAMEMODE_REPR_LIST", "GameMode")

GAMEMODE_REPR_LIST = (
    "vn!std",
    "vn!taiko",
    "vn!catch",
    "vn!mania",
    "rx!std",
    "rx!taiko",
    "rx!catch",
    "rx!mania",  # unused
    "ap!std",
    "ap!taiko",  # unused
    "ap!catch",  # unused
    "ap!mania",  # unused
)


@unique
@pymysql_encode(escape_enum)
class GameMode(IntEnum):
    VANILLA_OSU = 0
    VANILLA_TAIKO = 1
    VANILLA_CATCH = 2
    VANILLA_MANIA = 3

    RELAX_OSU = 4
    RELAX_TAIKO = 5
    RELAX_CATCH = 6
    RELAX_MANIA = 7  # unused

    AUTOPILOT_OSU = 8
    AUTOPILOT_TAIKO = 9  # unused
    AUTOPILOT_CATCH = 10  # unused
    AUTOPILOT_MANIA = 11  # unused

    @classmethod
    def from_params(cls, mode_vn: int, mods: Mods) -> GameMode:
        mode = mode_vn

        if mods & Mods.AUTOPILOT:
            mode += 8
        elif mods & Mods.RELAX:
            mode += 4

        return cls(mode)

    @classmethod
    @functools.cache
    def valid_gamemodes(cls) -> list[GameMode]:
        ret = []
        for mode in cls:
            if mode not in (
                cls.RELAX_MANIA,
                cls.AUTOPILOT_TAIKO,
                cls.AUTOPILOT_CATCH,
                cls.AUTOPILOT_MANIA,
            ):
                ret.append(mode)
        return ret

    @property
    def as_vanilla(self) -> int:
        return self.value % 4

    def __repr__(self) -> str:
        return GAMEMODE_REPR_LIST[self.value]
