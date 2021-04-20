# -*- coding: utf-8 -*-

import inspect
import pymysql
import requests
import sys
import types
from pathlib import Path
from typing import Callable
from typing import Sequence
from typing import Type

from cmyui.logging import Ansi
from cmyui.logging import log
from cmyui.logging import printc
from cmyui.osu.replay import Keys
from cmyui.osu.replay import ReplayFrame

__all__ = (
    'point_of_interest',
    'get_press_times',
    'make_safe_name',
    'download_achievement_pngs',
    'seconds_readable',
    'install_excepthook',

    'pymysql_encode',
    'escape_enum'
)

def point_of_interest():
    """Leave a pseudo-breakpoint somewhere to ask the user if
       they could pls submit their stacktrace to cmyui <3."""

    # TODO: fix this, circular import thing
    #ver_str = f'Running gulag v{glob.version!r} | cmyui_pkg v{cmyui.__version__}'
    #printc(ver_str, Ansi.LBLUE)

    for fi in inspect.stack()[1:]:
        if fi.function == '_run':
            # go all the way up to server start func
            break

        file = Path(fi.filename)

        # print line num, index, func name & locals for each frame.
        log('[{function}() @ {fname} L{lineno}:{index}] {frame.f_locals}'.format(
            **fi._asdict(), fname=file.name
        ))

    msg_str = '\n'.join((
        "Hey! If you're seeing this, osu! just did something pretty strange,",
        "and the gulag devs have left a breakpoint here. We'd really appreciate ",
        "if you could screenshot the data above, and send it to cmyui, either via ",
        "Discord (cmyui#0425), or by email (cmyuiosu@gmail.com). Thanks! 😳😳😳"
    ))

    printc(msg_str, Ansi.LRED)
    input('To close this menu & unfreeze, simply hit the enter key.')

useful_keys = (Keys.M1, Keys.M2,
               Keys.K1, Keys.K2)

def get_press_times(frames: Sequence[ReplayFrame]) -> dict[Keys, float]:
    """A very basic function to press times of an osu! replay.
       This is mostly only useful for taiko maps, since it
       doesn't take holds into account (taiko has none).

       In the future, we will make a version that can take
       account for the type of note that is being hit, for
       much more accurate and useful detection ability.
    """
    # TODO: remove negatives?
    press_times = {key: [] for key in useful_keys}
    cumulative = {key: 0 for key in useful_keys}

    prev_frame = frames[0]

    for frame in frames[1:]:
        for key in useful_keys:
            if frame.keys & key:
                # key pressed, add to cumulative
                cumulative[key] += frame.delta
            elif prev_frame.keys & key:
                # key unpressed, add to press times
                press_times[key].append(cumulative[key])
                cumulative[key] = 0

        prev_frame = frame

    # return all keys with presses
    return {k: v for k, v in press_times.items() if v}

def make_safe_name(name: str) -> str:
    """Return a name safe for usage in sql."""
    return name.lower().replace(' ', '_')

# TODO: async? lol
def download_achievement_pngs(medals_path: Path) -> None:
    achs = []

    for res in ('', '@2x'):
        for gm in ('osu', 'taiko', 'fruits', 'mania'):
            # only osu!std has 9 & 10 star pass/fc medals.
            for n in range(1, 1 + (10 if gm == 'osu' else 8)):
                achs.append(f'{gm}-skill-pass-{n}{res}.png')
                achs.append(f'{gm}-skill-fc-{n}{res}.png')

        for n in (500, 750, 1000, 2000):
            achs.append(f'osu-combo-{n}{res}.png')

    for ach in achs:
        r = requests.get(f'https://assets.ppy.sh/medals/client/{ach}')
        if r.status_code != 200:
            log(f'Failed to download achievement: {ach}', Ansi.LRED)
            continue

        log(f'Saving achievement: {ach}', Ansi.LCYAN)
        (medals_path / f'{ach}').write_bytes(r.content)

def seconds_readable(seconds: int) -> str:
    """Turn seconds as an int into 'DD:HH:MM:SS'."""
    r: list[str] = []

    days, seconds = divmod(seconds, 60 * 60 * 24)
    if days:
        r.append(f'{days:02d}')

    hours, seconds = divmod(seconds, 60 * 60)
    if hours:
        r.append(f'{hours:02d}')

    minutes, seconds = divmod(seconds, 60)
    r.append(f'{minutes:02d}')

    r.append(f'{seconds % 60:02d}')
    return ':'.join(r)

def install_excepthook():
    sys._excepthook = sys.excepthook # backup
    def _excepthook(
        type_: Type[BaseException],
        value: BaseException,
        traceback: types.TracebackType
    ):
        if type_ is KeyboardInterrupt:
            print('\33[2K\r', end='Aborted startup.')
            return
        print('\x1b[0;31mgulag ran into an issue '
            'before starting up :(\x1b[0m')
        sys._excepthook(type_, value, traceback)
    sys.excepthook = _excepthook

def pymysql_encode(conv: Callable):
    """Decorator to allow for adding to pymysql's encoders."""
    def wrapper(cls):
        pymysql.converters.encoders[cls] = conv
        return cls
    return wrapper

def escape_enum(val, mapping=None) -> str: # used for ^
    return str(int(val))
