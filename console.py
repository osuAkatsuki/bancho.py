from typing import Final
from enum import IntEnum
from datetime import datetime as dt, timezone as tz, timedelta as td

__all__ = (
    'Ansi',
    'get_timestamp',
    'printlog'
)

class Ansi(IntEnum):
    # Default colours
    BLACK: Final[int] = 30
    RED: Final[int] = 31
    GREEN: Final[int] = 32
    YELLOW: Final[int] = 33
    BLUE: Final[int] = 34
    MAGENTA: Final[int] = 35
    CYAN: Final[int] = 36
    WHITE: Final[int] = 37

    # Light colours
    GRAY: Final[int] = 90
    LIGHT_RED: Final[int] = 91
    LIGHT_GREEN: Final[int] = 92
    LIGHT_YELLOW: Final[int] = 93
    LIGHT_BLUE: Final[int] = 94
    LIGHT_MAGENTA: Final[int] = 95
    LIGHT_CYAN: Final[int] = 96
    LIGHT_WHITE: Final[int] = 97

    RESET: Final[int] = 0

    def __repr__(self) -> str:
        return f'\x1b[{self.value}m'

ts_fmt = ('%d/%m/%Y %I:%M:%S%p', '%I:%M:%S%p')
tz_est = tz(td(hours = -4), 'EDT')
def get_timestamp(full: bool = False) -> str:
    return f'{dt.now(tz = tz_est):{ts_fmt[full]}}'

# TODO: perhaps make some kind of
# timestamp class with __format__?

def printlog(msg, col: Ansi = None, fd: str = None, st_fmt = '') -> None:
    # This can be used both for logging purposes, or also just printing
    # with colour without having to do inline color codes / ansi objects.

    if st_fmt:
        print(st_fmt, end = '')

    if col:
        print(f'{Ansi.GRAY!r}[{get_timestamp(False)}] {col!r}{msg}{Ansi.RESET!r}')
    else:
        print(f'{Ansi.GRAY!r}[{get_timestamp(False)}]{Ansi.RESET!r} {msg}')

    if not fd:
        return

    with open(fd, 'a+') as f:
        f.write(f'[{get_timestamp(True)}] {msg}\n')
