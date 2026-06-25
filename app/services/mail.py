from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import unquote

from app.logging import Ansi
from app.logging import log
from app.objects.player import Player
from app.repositories.mail import MailRepository


class PlayerLookup(Protocol):
    async def from_cache_or_sql(
        self,
        id: int | None = None,
        name: str | None = None,
    ) -> Player | None: ...


@dataclass(frozen=True)
class MailReadService:
    mail: MailRepository
    players: PlayerLookup

    async def mark_channel_as_read(
        self,
        *,
        player: Player,
        channel: str,
    ) -> None:
        target_name = unquote(channel)  # TODO: unquote needed?
        if not target_name:
            log(
                f"User {player} attempted to mark a channel as read without a target.",
                Ansi.LYELLOW,
            )
            return

        target = await self.players.from_cache_or_sql(name=target_name)
        if target is not None:
            await self.mail.mark_conversation_as_read(
                to_id=player.id,
                from_id=target.id,
            )
