# -*- coding: utf-8 -*-

from typing import Final
from enum import IntEnum, unique

__all__ = 'osuTypes',

@unique
class osuTypes(IntEnum):
    # integral
    i8:  Final[int] = 0
    u8:  Final[int] = 1
    i16: Final[int] = 2
    u16: Final[int] = 3
    i32: Final[int] = 4
    u32: Final[int] = 5
    f32: Final[int] = 6
    i64: Final[int] = 7
    u64: Final[int] = 8
    f64: Final[int] = 9

    # osu
    message:        Final[int] = 11
    channel:        Final[int] = 12
    match:          Final[int] = 13
    scoreframe:     Final[int] = 14
    mapInfoRequest: Final[int] = 15
    mapInfoReply:   Final[int] = 16

    # misc
    i32_list:   Final[int] = 17 # 2 bytes len
    i32_list4l: Final[int] = 18 # 4 bytes len
    string:     Final[int] = 19
    raw:        Final[int] = 20
