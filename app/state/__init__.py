from typing import TYPE_CHECKING
from typing import TypedDict

from . import cache
from . import services
from . import sessions
from . import settings

if TYPE_CHECKING:
    from asyncio import AbstractEventLoop

loop: "AbstractEventLoop"
packets = {"all": {}, "restricted": {}}
shutting_down = False
