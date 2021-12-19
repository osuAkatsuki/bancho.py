# note that this is still a very rough draft of
# the concept and is subject to major refactoring
import random
from enum import IntEnum
from enum import unique
from typing import Awaitable
from typing import Callable
from typing import NamedTuple
from typing import Optional
from typing import TYPE_CHECKING
from typing import Union


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
    options: "dict[int, tuple[MenuCommands, Optional[Union[Menu, MenuFunction]]]]"


class MenuFunction(NamedTuple):
    name: str
    callback: Callable[["Player"], Awaitable[None]]


def menu_keygen() -> int:
    return random.randint(64, 0x7FFFFFFF)  # (max_matches, int32_max)
