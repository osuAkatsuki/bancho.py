from __future__ import annotations

from ipaddress import IPv4Address
from ipaddress import IPv6Address
from typing import Any
from typing import TypeVar
from typing import Union

IPAddress = Union[IPv4Address, IPv6Address]
T = TypeVar("T")


class _UnsetSentinel:
    def __repr__(self) -> str:
        return "Unset"

    def __copy__(self: T) -> T:
        return self

    def __reduce__(self) -> str:
        return "Unset"

    def __deepcopy__(self: T, _: Any) -> T:
        return self


UNSET = _UnsetSentinel()
