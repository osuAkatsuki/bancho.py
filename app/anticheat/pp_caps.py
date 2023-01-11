from __future__ import annotations

from typing import Optional

from app.constants.gamemodes import GameMode

#
# Anticheat checks can be defined here.
# The parameters are always the score object.
# The response is a string that is either None or the restriction reason.
#
# Here is an example for a pp cap rule:
async def std_ppcap(score: dict) -> Optional[str]:

    if score["mode"] != GameMode.VANILLA_OSU:
        return

    if score["pp"] >= 1500:
        return "Exceeded std!vn pp cap of 1500pp"