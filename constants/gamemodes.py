# -*- coding: utf-8 -*-

from enum import IntEnum, unique

__all__ = 'GameMode',

gm_str = (
    'vn!std',
    'vn!taiko',
    'vn!catch',
    'vn!mania',
    'rx!std',
    'rx!taiko',
    'rx!catch'
)

gm_sql = (
    'vn_std',
    'vn_taiko',
    'vn_catch',
    'vn_mania',
    'rx_std',
    'rx_taiko',
    'rx_catch'
)

@unique
class GameMode(IntEnum):
    """A class to represent a gamemode."""

    # Some inspiration taken
    # from rumoi/ruri here.
    vn_std   = 0
    vn_taiko = 1
    vn_catch = 2
    vn_mania = 3
    rx_std   = 4
    rx_taiko = 5
    rx_catch = 6

    def __str__(self) -> str:
        return gm_str[self.value]

    def __format__(self, fmt: str) -> str:
        return gm_sql[self.value] if fmt == 'sql' \
          else str(self.value)
