"""shared parameter types for bancho.py's v2 apis"""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator

from app.constants.gamemodes import GameMode


def _validate_gamemode(mode: int) -> int:
    if mode not in GameMode.valid_gamemodes():
        raise ValueError(
            "invalid gamemode; valid values are "
            f"{', '.join(str(int(m)) for m in GameMode.valid_gamemodes())}",
        )
    return mode


# a playable gamemode id (0-3 vanilla, 4-6 relax, 8 autopilot);
# 7 and 9-11 are rejected with a request validation error.
GameModeParam = Annotated[int, AfterValidator(_validate_gamemode)]
