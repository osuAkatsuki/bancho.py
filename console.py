from typing import Final
from enum import IntEnum
from datetime import datetime as dt, timezone as tz

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

def get_timestamp(full: bool = False) -> str:
    fmt = '%d/%m/%Y %I:%M:%S%p' if full else '%I:%M:%S:%p'
    return f'{dt.now(tz = tz.utc):{fmt}}'

# TODO: perhaps make some kind of
# timestamp class with __format__?
def printc(msg, col: Ansi, fd: str = 'log/chat.log',
           st_fmt = '') -> None:
    if fd:
        with open(fd, 'a+') as f:
            f.write(f'[{get_timestamp(True)}] {msg}')
    print(f'{st_fmt}{col!r}[{get_timestamp(False)}] {msg}{Ansi.RESET!r}')
