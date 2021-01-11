# -*- coding: utf-8 -*-

import inspect

import cmyui
from cmyui.logging import log, printc, Ansi
from pathlib import Path

from objects import glob

def point_of_interest():
    """Leave a pseudo-breakpoint somewhere to ask the user if
       they could pls submit their stacktrace to cmyui <3."""

    ver_str = f'Running gulag v{glob.version!r} | cmyui_pkg v{cmyui.__version__}'
    printc(ver_str, Ansi.LBLUE)

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
