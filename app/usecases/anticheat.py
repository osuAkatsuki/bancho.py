from __future__ import annotations

import inspect
import sys
from typing import Optional

import app.logging
import app.state.sessions
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.constants.privileges import Privileges
from app.objects.player import Player
from app.objects.score import Score
# DO NOT import non-anticheat check functions directly, it'll mess up inspect.getmembers
# You can create separate .py files containing more checks for a better hierarchy
# and import them here, e.g. with import example_check from app.usecases.anticheat.pp_caps


async def run_anticheat_checks(player: Player, score: Score):
    checks = dict(inspect.getmembers(sys.modules[__name__], inspect.isfunction))
    checks.pop("run_anticheat_checks")

    for (name, callable) in checks.items():
        # Get the result from the check callable
        result = await callable(player, score)
        if result:
            player.restrict(app.state.sessions.bot, result)
            app.logging.log(
                f"{player} has been restricted through anticheat check '{name}' (reason: {result})",
                app.logging.Ansi.CYAN,
            )


#
# Anticheat checks can be defined here.
# The parameters are always the player and the score object.
# The response is a string that is either None or the restriction reason.
#
# Here is an example for a pp cap rule:
async def std_ppcap(player: Player, score: Score) -> Optional[str]:

    if score.mode != GameMode.VANILLA_OSU:
        return

    if score.pp >= 1500:
        return "Exceeded std!vn pp cap of 1500pp"
