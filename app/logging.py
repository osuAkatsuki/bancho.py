from __future__ import annotations

import colorsys
import datetime
import logging.config
from enum import IntEnum
from zoneinfo import ZoneInfo

import yaml


def configure_logging() -> None:
    with open("logging.yaml") as f:
        config = yaml.safe_load(f.read())
        logging.config.dictConfig(config)


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
    def __init__(self, *args: int) -> None:
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


class _Rainbow: ...


Rainbow = _Rainbow()

Colour_Types = Ansi | RGB | _Rainbow


def get_timestamp(full: bool = False, tz: ZoneInfo | None = None) -> str:
    fmt = "%d/%m/%Y %I:%M:%S%p" if full else "%I:%M:%S%p"
    return f"{datetime.datetime.now(tz=tz):{fmt}}"


# TODO: better solution than this; this at least requires the
# iana/tzinfo database to be installed, meaning it's limited.
_log_tz = ZoneInfo("GMT")  # default


def set_timezone(tz: ZoneInfo) -> None:
    global _log_tz
    _log_tz = tz


ROOT_LOGGER = logging.getLogger()


def log(
    msg: str,
    col: Colour_Types | None = None,
    file: str | None = None,
) -> None:
    """\
    Print a string, in a specified ansi colour with timestamp.

    Allows for the functionality to write to a file as
    well by passing the filepath with the `file` parameter.
    """

    if col is Ansi.GRAY:
        log_level = logging.INFO
    elif col is Ansi.LYELLOW:
        log_level = logging.WARNING
    elif col is Ansi.LRED:
        log_level = logging.ERROR
    else:
        if col is None:
            col = Ansi.GRAY
        log_level = logging.INFO

    ROOT_LOGGER.log(log_level, f"{col!r}{msg}{Ansi.RESET!r}")

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


TIME_ORDER_SUFFIXES = ["nsec", "μsec", "msec", "sec"]


def magnitude_fmt_time(nanosec: int | float) -> str:
    suffix = None
    for suffix in TIME_ORDER_SUFFIXES:
        if nanosec < 1000:
            break
        nanosec /= 1000
    return f"{nanosec:.2f} {suffix}"
