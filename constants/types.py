# -*- coding: utf-8 -*-

from enum import IntEnum, unique

__all__ = ('osuTypes',)

@unique
class osuTypes(IntEnum):
    # integral
    i8  = 0
    u8  = 1
    i16 = 2
    u16 = 3
    i32 = 4
    u32 = 5
    f32 = 6
    i64 = 7
    u64 = 8
    f64 = 9

    # osu
    message = 11
    channel = 12
    match = 13
    scoreframe = 14

    # misc
    i32_list = 17
    string = 18
    raw = 19
