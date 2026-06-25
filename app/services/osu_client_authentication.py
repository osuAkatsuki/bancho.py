from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.objects.player import Player


class OnlinePlayers(Protocol):
    def get(
        self,
        token: str | None = None,
        id: int | None = None,
        name: str | None = None,
    ) -> Player | None: ...


@dataclass(frozen=True)
class OsuClientAuthenticationService:
    online_players: OnlinePlayers
    password_cache: dict[bytes, bytes]

    async def authenticate_online_player(
        self,
        *,
        username: str,
        password_md5: str,
    ) -> Player | None:
        player = self.online_players.get(name=username)
        if player is None or player.pw_bcrypt is None:
            return None

        if self.password_cache.get(player.pw_bcrypt) != password_md5.encode():
            return None

        return player
