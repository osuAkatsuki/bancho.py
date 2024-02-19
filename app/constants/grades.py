from __future__ import annotations

import functools
from enum import IntEnum
from enum import unique


@unique
class Grade(IntEnum):
    # NOTE: these are implemented in the opposite order
    # as osu! to make more sense with <> operators.
    N = 0
    F = 1
    D = 2
    C = 3
    B = 4
    A = 5
    S = 6  # S
    SH = 7  # HD S
    X = 8  # SS
    XH = 9  # HD SS

    @classmethod
    @functools.cache
    def from_str(cls, s: str) -> Grade:
        return {
            "xh": Grade.XH,
            "x": Grade.X,
            "sh": Grade.SH,
            "s": Grade.S,
            "a": Grade.A,
            "b": Grade.B,
            "c": Grade.C,
            "d": Grade.D,
            "f": Grade.F,
            "n": Grade.N,
        }[s.lower()]

    def __format__(self, format_spec: str) -> str:
        if format_spec == "stats_column":
            return f"{self.name.lower()}_count"
        else:
            raise ValueError(f"Invalid format specifier {format_spec}")
