from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field

from app.objects.collections import Channels
from app.objects.collections import Matches
from app.objects.collections import Players
from app.objects.player import Player


@dataclass
class SessionState:
    """The mutable in-memory state for one running bancho application."""

    players: Players
    channels: Channels
    matches: Matches
    bot: Player
    api_keys: dict[str, int] = field(default_factory=dict)
