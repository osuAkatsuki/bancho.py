from __future__ import annotations

from ipaddress import IPv4Address
from ipaddress import IPv6Address
from typing import Any
from typing import TypeVar

from typing_extensions import override

T = TypeVar("T")

IPAddress = IPv4Address | IPv6Address


class Unset:
    @override
    def __repr__(self) -> str:
        return "Unset"

    def __copy__(self: T) -> T:
        return self

    @override
    def __reduce__(self) -> str:
        return "Unset"

    def __deepcopy__(self: T, _: Any) -> T:
        return self


UNSET = Unset()
