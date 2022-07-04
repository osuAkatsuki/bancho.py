from __future__ import annotations

from asyncio import AbstractEventLoop

from . import cache
from . import services
from . import sessions

loop: AbstractEventLoop
packets = {"all": {}, "restricted": {}}
shutting_down = False
