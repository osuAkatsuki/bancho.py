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
    def __init__(self, rgb: int) -> None:
        ...

    @overload
    def __init__(self, r: int, g: int, b: int) -> None:
        ...

    def __init__(self, *args) -> None:
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


class _Rainbow:
    ...


Rainbow = _Rainbow()

Colour_Types = Union[Ansi, RGB, _Rainbow]


def get_timestamp(full: bool = False, tz: Optional[datetime.tzinfo] = None) -> str:
    fmt = "%d/%m/%Y %I:%M:%S%p" if full else "%I:%M:%S%p"
    return f"{datetime.datetime.now(tz=tz):{fmt}}"


# TODO: better solution than this; this at least requires the
# iana/tzinfo database to be installed, meaning it's limited.
_log_tz = ZoneInfo("GMT")  # default


def set_timezone(tz: datetime.tzinfo) -> None:
    global _log_tz
    _log_tz = tz


def printc(msg: str, col: Colour_Types, end: str = "\n") -> None:
    """Print a string, in a specified ansi colour."""
    print(f"{col!r}{msg}{Ansi.RESET!r}", end=end)


def log(
    msg: str,
    col: Optional[Colour_Types] = None,
    file: Optional[str] = None,
    end: str = "\n",
) -> None:
    """\
    Print a string, in a specified ansi colour with timestamp.

    Allows for the functionality to write to a file as
    well by passing the filepath with the `file` parameter.
    """

    ts_short = get_timestamp(full=False, tz=_log_tz)

    if col:
        if col is Rainbow:
            print(f"{Ansi.GRAY!r}[{ts_short}] {_fmt_rainbow(msg, 2/3)}", end=end)
            print(f"{Ansi.GRAY!r}[{ts_short}] {_fmt_rainbow(msg, 2/3)}", end=end)
        else:
            # normal colour
            print(f"{Ansi.GRAY!r}[{ts_short}] {col!r}{msg}{Ansi.RESET!r}", end=end)
    else:
        print(f"{Ansi.GRAY!r}[{ts_short}]{Ansi.RESET!r} {msg}", end=end)

    if file:
        # log simple ascii output to file.
        with open(file, "a+") as f:
            f.write(f"[{get_timestamp(full=True, tz=_log_tz)}] {msg}\n")


def rainbow_color_stops(
    n: int = 10,
    lum: float = 0.5,
    end: float = 2 / 3,
) -> list[tuple[float, float, float]]:
    return [
        (r * 255, g * 255, b * 255)
        for r, g, b in [
            colorsys.hls_to_rgb(end * i / (n - 1), lum, 1) for i in range(n)
        ]
    ]


def _fmt_rainbow(msg: str, end: float = 2 / 3) -> str:
    cols = [RGB(*map(int, rgb)) for rgb in rainbow_color_stops(n=len(msg), end=end)]
    return "".join([f"{cols[i]!r}{c}" for i, c in enumerate(msg)]) + repr(Ansi.RESET)


def print_rainbow(msg: str, rainbow_end: float = 2 / 3, end: str = "\n") -> None:
    print(_fmt_rainbow(msg, rainbow_end), end=end)


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
