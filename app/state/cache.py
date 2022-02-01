from typing import TYPE_CHECKING
from typing import Union

if TYPE_CHECKING:
    from ipaddress import IPv4Address, IPv6Address

    from app.objects.beatmap import Beatmap, BeatmapSet

    IPAddress = Union[IPv4Address, IPv6Address]

bcrypt: dict[bytes, bytes] = {}  # {bcrypt: md5, ...}
ip: dict[str, "IPAddress"] = {}  # {ip_str: IPAddress, ...}
beatmap: dict[Union[str, int], "Beatmap"] = {}  # {md5: map, id: map, ...}
beatmapset: dict[int, "BeatmapSet"] = {}  # {bsid: map_set}
unsubmitted: set[str] = set()  # {md5, ...}
needs_update: set[str] = set()  # {md5, ...}
