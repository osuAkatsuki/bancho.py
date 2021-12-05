from typing import TYPE_CHECKING

from app.objects.collections import Channels
from app.objects.collections import Clans
from app.objects.collections import MapPools
from app.objects.collections import Matches
from app.objects.collections import Players

if TYPE_CHECKING:
    from app.objects.achievement import Achievement
    from app.objects.player import Player

players = Players()
channels = Channels()
matches = Matches()
clans = Clans()
pools = MapPools()
achievements: list["Achievement"] = []

bot: "Player"
