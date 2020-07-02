# -*- coding: utf-8 -*-

from enum import IntEnum, unique

@unique
class ctypes(IntEnum):
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

    i32_list = 10
    string = 11
    raw = 12
