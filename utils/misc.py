# -*- coding: utf-8 -*-

import dill as pickle
import inspect
import io
import pymysql
import requests
import secrets
import sys
import types
import zipfile
from pathlib import Path
from typing import Callable
from typing import Sequence
from typing import Type

from objects import glob
from cmyui.logging import Ansi
from cmyui.logging import log
from cmyui.logging import printc
from cmyui.osu.replay import Keys
from cmyui.osu.replay import ReplayFrame

__all__ = (
    'get_press_times',
    'make_safe_name',
    'download_achievement_images',
    'seconds_readable',
    'install_excepthook',
    'get_appropriate_stacktrace',
    'log_strange_occurrence',

    'pymysql_encode',
    'escape_enum'
)

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

def _download_achievement_images_mirror(achievements_path: Path) -> bool:
    """Download all used achievement images (using mirror's zip)."""
    log('Downloading achievement images from mirror.', Ansi.LCYAN)
    r = requests.get('https://cmyui.xyz/achievement_images.zip')

    if r.status_code != 200:
        log('Failed to fetch from mirror, trying osu! servers.', Ansi.LRED)
        return False

    with io.BytesIO(r.content) as data:
        with zipfile.ZipFile(data) as myfile:
            myfile.extractall(achievements_path)

    return True

def _download_achievement_images_osu(achievements_path: Path) -> bool:
    """Download all used achievement images (one by one, from osu!)."""
    achs = []

    for res in ('', '@2x'):
        for gm in ('osu', 'taiko', 'fruits', 'mania'):
            # only osu!std has 9 & 10 star pass/fc medals.
            for n in range(1, 1 + (10 if gm == 'osu' else 8)):
                achs.append(f'{gm}-skill-pass-{n}{res}.png')
                achs.append(f'{gm}-skill-fc-{n}{res}.png')

        for n in (500, 750, 1000, 2000):
            achs.append(f'osu-combo-{n}{res}.png')

    log('Downloading achievement images from osu!.', Ansi.LCYAN)

    for ach in achs:
        r = requests.get(f'https://assets.ppy.sh/medals/client/{ach}')
        if r.status_code != 200:
            return False

        log(f'Saving achievement: {ach}', Ansi.LCYAN)
        (achievements_path / f'{ach}').write_bytes(r.content)

    return True

def download_achievement_images(achievements_path: Path) -> None:
    """Download all used achievement images (using best available source)."""
    # try using my cmyui.xyz mirror (zip file)
    downloaded = _download_achievement_images_mirror(achievements_path)

    if not downloaded:
        # as fallback, download individual files from osu!
        downloaded = _download_achievement_images_osu(achievements_path)

    if downloaded:
        log('Successfully saved all achievement images.', Ansi.LGREEN)
    else:
        # TODO: make the code safe in this state
        log('Failed to download achievement images.', Ansi.LRED)
        achievements_path.rmdir()

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
    """Install a thin wrapper for sys.excepthook to catch gulag-related stuff."""
    sys._excepthook = sys.excepthook # backup
    def _excepthook(
        type_: Type[BaseException],
        value: BaseException,
        traceback: types.TracebackType
    ):
        if type_ is KeyboardInterrupt:
            print('\33[2K\r', end='Aborted startup.')
            return
        elif (
            type_ is AttributeError and
            value.args[0].startswith("module 'config' has no attribute")
        ):
            attr_name = value.args[0][34:-1]
            log("gulag's config has been updated, and has "
                f"added a new `{attr_name}` attribute.", Ansi.LMAGENTA)
            log("Please refer to it's value & example in "
                "ext/config.sample.py for additional info.", Ansi.LCYAN)
            return

        print('\x1b[0;31mgulag ran into an issue '
            'before starting up :(\x1b[0m')
        sys._excepthook(type_, value, traceback)
    sys.excepthook = _excepthook

def get_appropriate_stacktrace() -> list[inspect.FrameInfo]:
    stack = inspect.stack()[1:]
    for idx, frame in enumerate(stack):
        if frame.function == 'run':
            break
    else:
        raise Exception

    return [{
        'function': frame.function,
        'filename': Path(frame.filename).name,
        'lineno': frame.lineno,
        'charno': frame.index,
        'locals': {k: repr(v) for k, v in frame.frame.f_locals.items()}
    } for frame in stack[:idx]]

STRANGE_LOG_DIR = Path.cwd() / '.data/logs'
async def log_strange_occurrence(obj: object) -> None:
    pickled_obj = pickle.dumps(obj)
    uploaded = False

    if glob.config.automatically_report_problems:
        # automatically reporting problems to cmyui's server
        async with glob.http.post(
            url = 'https://log.cmyui.xyz/',
            headers = {'Gulag-Version': repr(glob.version),
                       'Gulag-Domain': glob.config.domain},
            data = pickled_obj,
        ) as resp:
            if (
                resp.status == 200 and
                (await resp.read()) == b'ok'
            ):
                uploaded = True
                log("Logged strange occurrence to cmyui's server.", Ansi.LBLUE)
                log("Thank you for your participation! <3", Ansi.LBLUE)
            else:
                log(f"Autoupload to cmyui's server failed (HTTP {resp.status})", Ansi.LRED)

    if not uploaded:
        # log to a file locally, and prompt the user
        while True:
            log_file = STRANGE_LOG_DIR / f'strange_{secrets.token_hex(4)}.db'
            if not log_file.exists():
                break

        log_file.touch(exist_ok=False)
        log_file.write_bytes(pickled_obj)

        log('Logged strange occurrence to', Ansi.LYELLOW, end=' ')
        printc('/'.join(log_file.parts[-4:]), Ansi.LBLUE)

        log("Greatly appreciated if you could forward this to cmyui#0425 :)", Ansi.LYELLOW)

def pymysql_encode(conv: Callable):
    """Decorator to allow for adding to pymysql's encoders."""
    def wrapper(cls):
        pymysql.converters.encoders[cls] = conv
        return cls
    return wrapper

def escape_enum(val, mapping=None) -> str: # used for ^
    return str(int(val))
