# note that this is still a very rough draft of
# the concept and is subject to major refactoring
from __future__ import annotations

import random
from collections.abc import Awaitable
from collections.abc import Callable
from enum import IntEnum
from enum import unique
from typing import NamedTuple
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from app.objects.player import Player


@unique
class MenuCommands(IntEnum):
    Reset = 0  # go to main menu
    Back = 1  # go to previous menu
    Advance = 2  # go to new menu
    Execute = 3  # execute a function on current menu


class Menu(NamedTuple):
    name: str
    options: dict[int, tuple[MenuCommands, Menu | MenuFunction | None]]


class MenuFunction(NamedTuple):
    name: str
    callback: Callable[[Player], Awaitable[None]]


def menu_keygen() -> int:
    return random.randint(64, 0x7FFFFFFF)  # (max_matches, int32_max)
