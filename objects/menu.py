# note that this is still a very rough draft of
# the concept and is subject to major refactoring

import random
from enum import IntEnum
from enum import unique
from typing import Callable
from typing import Coroutine
from typing import NamedTuple
from typing import TYPE_CHECKING
from typing import Union

from objects import glob

if TYPE_CHECKING:
    from objects.player import Player

@unique
class MenuCommands(IntEnum):
    Reset = 0 # go to main menu
    Back = 1 # go to previous menu
    Advance = 2 # go to new menu
    Execute = 3 # execute a function on current menu

class Menu(NamedTuple):
    name: str
    options: dict[int, tuple[MenuCommands, Union['Menu', 'MenuFunction', None]]]

class MenuFunction(NamedTuple):
    name: str
    callback: Callable[['Player'], Coroutine[None, None, None]]

def menu_keygen() -> int:
    min_key = glob.config.max_multi_matches
    return random.randint(min_key, 0x7fffffff)
