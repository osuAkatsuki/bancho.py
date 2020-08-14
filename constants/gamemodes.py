# -*- coding: utf-8 -*-

from typing import Final
from enum import IntEnum, unique

__all__ = ('GameMode',)

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
        return (
            'vn!std',
            'vn!taiko',
            'vn!catch',
            'vn!mania',
            'rx!std',
            'rx!taiko',
            'rx!catch'
        )[self.value]

    def __format__(self, format: str) -> str:
        return (
            'vn_std',
            'vn_taiko',
            'vn_catch',
            'vn_mania',
            'rx_std',
            'rx_taiko',
            'rx_catch'
        )[self.value] if format == 'sql' else str(self.value)
