from __future__ import annotations

import colorsys
import datetime
from enum import IntEnum
from typing import Optional
from typing import overload
from typing import Union
from zoneinfo import ZoneInfo


class Ansi(IntEnum):
    # Default colours
    BLACK = 30
    RED = 31
    GREEN = 32
    YELLOW = 33
    BLUE = 34
    MAGENTA = 35
    CYAN = 36
    WHITE = 37

    # Light colours
    GRAY = 90
    LRED = 91
    LGREEN = 92
    LYELLOW = 93
    LBLUE = 94
    LMAGENTA = 95
    LCYAN = 96
    LWHITE = 97

    RESET = 0

    def __repr__(self) -> str:
        return f"\x1b[{self.value}m"


class RGB:
    @overload
    def __init__(self, rgb: int, **kwargs) -> None:
        ...

    @overload
    def __init__(self, r: int, g: int, b: int, **kwargs) -> None:
        ...

    def __init__(self, *args, **kwargs) -> None:
        largs = len(args)

        if largs == 3:
            # r, g, b passed.
            self.r, self.g, self.b = args
        elif largs == 1:
            # passed as single argument
            rgb = args[0]
            self.b = rgb & 0xFF
            self.g = (rgb >> 8) & 0xFF
            self.r = (rgb >> 16) & 0xFF
        else:
            raise ValueError("Incorrect params for RGB.")

    def __repr__(self) -> str:
        return f"\x1b[38;2;{self.r};{self.g};{self.b}m"


def get_timestamp(full: bool = False, tz: Optional[datetime.tzinfo] = None) -> str:
    fmt = "%d/%m/%Y %I:%M:%S%p" if full else "%I:%M:%S%p"
    return f"{datetime.datetime.now(tz=tz):{fmt}}"


# TODO: better solution than this; this at least requires the
# iana/tzinfo database to be installed, meaning it's limited.
_log_tz = ZoneInfo("GMT")  # default


def set_timezone(tz: datetime.tzinfo) -> None:
    global _log_tz
    _log_tz = tz


def ansi_rgb_rainbow(msg: str, end: float = 2 / 3) -> str:
    """Add ANSI colour escapes to `msg` to make it a rainbow."""
    colours = [
        RGB(int(r * 255), int(g * 255), int(b * 255))
        for r, g, b in [
            colorsys.hls_to_rgb(h=end * i / (len(msg) - 1), l=0.5, s=1)
            for i in range(len(msg))
        ]
    ]

    return "".join([f"{colours[i]!r}{c}" for i, c in enumerate(msg)]) + repr(Ansi.RESET)


# TODO: genericize this to all SI measurements?

# TODO: support all named orders of magnitude?
# https://en.wikipedia.org/wiki/Metric_prefix
TIME_ORDER_SUFFIXES = ["nsec", "μsec", "msec", "sec"]


def magnitude_fmt_time(t: Union[int, float]) -> str:  # in nanosec
    for suffix in TIME_ORDER_SUFFIXES:
        if t < 1000:
            break
        t /= 1000
    return f"{t:.2f} {suffix}"  # type: ignore
