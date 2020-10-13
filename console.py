from enum import IntEnum, unique
from typing import Union, overload
from cmyui import get_timestamp

__all__ = 'Ansi', 'AnsiRGB', 'plog'

@unique
class Ansi(IntEnum):
    # default colours
    BLACK   = 30
    RED     = 31
    GREEN   = 32
    YELLOW  = 33
    BLUE    = 34
    MAGENTA = 35
    CYAN    = 36
    WHITE   = 37

    # light colours
    GRAY          = 90
    LRED     = 91
    LGREEN   = 92
    LYELLOW  = 93
    LBLUE    = 94
    LMAGENTA = 95
    LCYAN    = 96
    LWHITE   = 97

    RESET = 0

    def __repr__(self) -> str:
        return f'\x1b[{self.value}m'

class AnsiRGB:
    @overload
    def __init__(self, rgb: int) -> None: ...
    @overload
    def __init__(self, r: int, g: int, b: int) -> None: ...

    def __init__(self, *args) -> None:
        largs = len(args)

        if largs == 3:
            # r, g, b passed.
            self.r, self.g, self.b = args
        elif largs == 1:
            # passed as single argument
            rgb = args[0]
            self.b = rgb & 0xff
            self.g = (rgb >> 8) & 0xff
            self.r = (rgb >> 16) & 0xff
        else:
            raise Exception('Incorrect params for AnsiRGB.')

    def __repr__(self) -> str:
        return f'\x1b[38;2;{self.r};{self.g};{self.b}m'

def plog(msg, col: Union[Ansi, AnsiRGB] = None,
         fd: str = None, st_fmt = '') -> None:
    # this can be used both for logging purposes,
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

    # i think making the log a coroutine is going a
    # bit far; i'll take a possible performance hit
    # when we're debugging for much cleaner code :P
    with open(fd, 'a+') as f:
        f.write(f'[{get_timestamp(True)}] {msg}\n')
