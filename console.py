import aiofiles
from typing import Final
from enum import IntEnum, unique
from cmyui.utils import get_timestamp

__all__ = 'Ansi', 'plog'

@unique
class Ansi(IntEnum):
    # Default colours
    BLACK:   Final[int] = 30
    RED:     Final[int] = 31
    GREEN:   Final[int] = 32
    YELLOW:  Final[int] = 33
    BLUE:    Final[int] = 34
    MAGENTA: Final[int] = 35
    CYAN:    Final[int] = 36
    WHITE:   Final[int] = 37

    # Light colours
    GRAY:          Final[int] = 90
    LIGHT_RED:     Final[int] = 91
    LIGHT_GREEN:   Final[int] = 92
    LIGHT_YELLOW:  Final[int] = 93
    LIGHT_BLUE:    Final[int] = 94
    LIGHT_MAGENTA: Final[int] = 95
    LIGHT_CYAN:    Final[int] = 96
    LIGHT_WHITE:   Final[int] = 97

    RESET: Final[int] = 0

    def __repr__(self) -> str:
        return f'\x1b[{self.value}m'

async def plog(msg, col: Ansi = None,
                   fd: str = None, st_fmt = '') -> None:
    # This can be used both for logging purposes,
    # or also just printing with colour without having
    # to do inline color codes / ansi objects.

    if st_fmt:
        print(st_fmt, end = '')

    print('{gray!r}[{ts}] {col!r}{msg}{reset!r}'.format(
        gray = Ansi.GRAY,
        ts = get_timestamp(full = False),
        col = col if col else Ansi.RESET,
        msg = msg,
        reset = Ansi.RESET
    ))

    if not fd:
        return

    async with aiofiles.open(fd, 'a+') as f:
        await f.write(f'[{get_timestamp(True)}] {msg}\n')
