from typing import TYPE_CHECKING

from mount.app.objects.collections import Channels
from mount.app.objects.collections import Clans
from mount.app.objects.collections import MapPools
from mount.app.objects.collections import Matches
from mount.app.objects.collections import Players

if TYPE_CHECKING:
    from mount.app.objects.achievement import Achievement
    from mount.app.objects.player import Player

players = Players()
channels = Channels()
matches = Matches()
clans = Clans()
pools = MapPools()
achievements: list["Achievement"] = []
api_keys = {}  # TODO: cleanup

bot: "Player"
