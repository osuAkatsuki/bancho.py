# -*- coding: utf-8 -*-

from typing import Final, Tuple
from enum import IntEnum, unique

__all__ = 'GameMode',

gm_str: Tuple[str, ...] = (
    'vn!std',
    'vn!taiko',
    'vn!catch',
    'vn!mania',
    'rx!std',
    'rx!taiko',
    'rx!catch'
)

gm_sql: Tuple[str, ...] = (
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
    vn_std:   Final[int] = 0
    vn_taiko: Final[int] = 1
    vn_catch: Final[int] = 2
    vn_mania: Final[int] = 3
    rx_std:   Final[int] = 4
    rx_taiko: Final[int] = 5
    rx_catch: Final[int] = 6

    def __str__(self) -> str:
        return gm_str[self.value]

    def __format__(self, fmt: str) -> str:
        return gm_sql[self.value] if fmt == 'sql' \
          else str(self.value)
