from app.objects.player import Player
from app.objects.score import Score
from app.constants.gamemodes import GameMode
from typing import Optional

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