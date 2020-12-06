# -*- coding: utf-8 -*-

import inspect

from pathlib import Path
from cmyui.logging import log, printc, Ansi

def point_of_interest():
    """Leave a pseudo-breakpoint somewhere to ask the user if
       they could pls submit their stacktrace to cmyui <3."""
    for fi in inspect.stack()[1:]:
        if fi.function == '_run':
            # go all the way up to server start func
            break

        file = Path(fi.filename)

        # print line num, index, func name & locals for each frame.
        log(f'[{fi.function}() @ {file.name} L{fi.lineno}:{fi.index}] {fi.frame.f_locals}', Ansi.LBLUE)

    msg = '\n'.join((
        "Hey! If you're seeing this, osu! just did something pretty strange,",
        "and the gulag devs have left a breakpoint here. We'd really appreciate ",
        "if you could screenshot the data above, and send it to cmyui, either via ",
        "Discord (cmyui#0425), or by email (cmyuiosu@gmail.com). Thanks! 😳😳😳"
    ))

    printc(msg, Ansi.LRED)
    input('To close this menu & unfreeze, simply hit the enter key.')
