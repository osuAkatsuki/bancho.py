# isort: dont-add-imports

import asyncio
from collections import defaultdict
from typing import TYPE_CHECKING
from typing import Literal

from . import cache
from . import services
from . import sessions

if TYPE_CHECKING:
    from asyncio import AbstractEventLoop

    from app.packets import BasePacket
    from app.packets import ClientPackets

loop: AbstractEventLoop
score_submission_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
packets: dict[Literal["all", "restricted"], dict[ClientPackets, type[BasePacket]]] = {
    "all": {},
    "restricted": {},
}
shutting_down = False
