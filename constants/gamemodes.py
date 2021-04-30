# -*- coding: utf-8 -*-

from enum import IntEnum
from enum import unique

from constants.mods import Mods
from utils.misc import pymysql_encode
from utils.misc import escape_enum

__all__ = ('GameMode',)

gm_str = (
    'vn!std',
    'vn!taiko',
    'vn!catch',
    'vn!mania',

    'rx!std',
    'rx!taiko',
    'rx!catch',

    'ap!std'
)

gm_sql = (
    'vn_std',
    'vn_taiko',
    'vn_catch',
    'vn_mania',

    'rx_std',
    'rx_taiko',
    'rx_catch',

    'ap_std'
)

@unique
@pymysql_encode(escape_enum)
class GameMode(IntEnum):
    vn_std   = 0
    vn_taiko = 1
    vn_catch = 2
    vn_mania = 3

    rx_std   = 4
    rx_taiko = 5
    rx_catch = 6

    ap_std   = 7

    @classmethod
    def from_params(cls, mode_vn: int, mods: Mods) -> 'GameMode':
        mode = mode_vn
        if mods & Mods.RELAX:
            mode += 4

        elif mods & Mods.AUTOPILOT:
            mode += 7

        if mode > 7: # don't apply mods if invalid
            return cls(mode_vn)

        return cls(mode)

    @property
    def sql_table(self) -> str:
        if self.value < self.rx_std:
            return 'scores_vn'
        elif self.value < self.ap_std:
            return 'scores_rx'
        else:
            return 'scores_ap'

    @property
    def as_vanilla(self) -> int:
        if self.value == self.ap_std:
            return 0

        return self.value % 4

    def __repr__(self) -> str:
        return gm_str[self.value]

    def __format__(self, fmt: str) -> str:
        if fmt == 'sql':
            return gm_sql[self.value]
        else:
            return str(self.value)
