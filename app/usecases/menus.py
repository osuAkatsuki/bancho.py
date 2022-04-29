from __future__ import annotations

import random

MENU_ID_START = 2_000_000_000
INT32_MAX = 0x7FFFFFFF


def menu_keygen() -> int:
    return random.randint(MENU_ID_START, INT32_MAX)
