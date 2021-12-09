from typing import TYPE_CHECKING

from . import services
from . import sessions
from . import settings

if TYPE_CHECKING:
    from asyncio.events import AbstractEventLoop

loop: "AbstractEventLoop"
packets = {"all": {}, "restricted": {}}
shutting_down = False


# class Cache(TypedDict):
#     bcrypt: dict[bytes, bytes]

#     ip: dict[str, "IPAddress"]

#     beatmap: dict[str | int, "Beatmap"]  # bid & md5 keys
#     beatmapset: dict[int, "BeatmapSet"]  # bsid keys

#     unsubmitted: set[str]
#     needs_update: set[str]


cache: "Cache" = {
    "bcrypt": {},  # {bcrypt: md5, ...}
    "ip": {},  # {ip_str: IPAddress, ...}
    "beatmap": {},  # {md5: map, id: map, ...}
    "beatmapset": {},  # {bsid: map_set}
    "unsubmitted": set(),  # {md5, ...}
    "needs_update": set(),  # {md5, ...}
}
