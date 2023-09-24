from __future__ import annotations

from typing import Literal
from typing import TYPE_CHECKING

from . import cache
from . import services
from . import sessions

if TYPE_CHECKING:
    from asyncio import AbstractEventLoop
    from app.packets import ClientPackets
    from app.packets import BasePacket

loop: AbstractEventLoop
packets: dict[Literal["all", "restricted"], dict[ClientPackets, type[BasePacket]]] = {
    "all": {},
    "restricted": {},
}
shutting_down = False
