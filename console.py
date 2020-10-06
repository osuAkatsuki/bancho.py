import aiofiles
from enum import IntEnum, unique
from cmyui import get_timestamp

__all__ = 'Ansi', 'plog'

@unique
class Ansi(IntEnum):
    # Default colours
    BLACK   = 30
    RED     = 31
    GREEN   = 32
    YELLOW  = 33
    BLUE    = 34
    MAGENTA = 35
    CYAN    = 36
    WHITE   = 37

    # Light colours
    GRAY          = 90
    LIGHT_RED     = 91
    LIGHT_GREEN   = 92
    LIGHT_YELLOW  = 93
    LIGHT_BLUE    = 94
    LIGHT_MAGENTA = 95
    LIGHT_CYAN    = 96
    LIGHT_WHITE   = 97

    RESET = 0

    def __repr__(self) -> str:
        return f'\x1b[{self.value}m'

# yea that's right, even the log is a coroutine lol
async def plog(msg, col: Ansi = None,
               fd: str = None, st_fmt = '') -> None:
    # This can be used both for logging purposes,
    # or also just printing with colour without having
    # to do inline colour codes / ansi objects.

    if st_fmt:
        print(st_fmt, end = '')

    print('{gray!r}[{ts}] {col!r}{msg}{reset!r}'.format(
        gray = Ansi.GRAY,
        ts = get_timestamp(full = False),
        col = col or Ansi.RESET,
        msg = msg,
        reset = Ansi.RESET
    ))

    if not fd:
        return

    async with aiofiles.open(fd, 'a+') as f:
        await f.write(f'[{get_timestamp(True)}] {msg}\n')
