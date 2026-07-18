from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.constants.privileges import Privileges
from app.logging import log
from app.objects.player import Player
from app.repositories.comments import CommentsRepository
from app.repositories.comments import CommentWithUserPrivileges
from app.repositories.comments import TargetType


@dataclass(frozen=True)
class CommentsService:
    comments: CommentsRepository
    schedule_latest_activity_update: Callable[[Player], None]

    async def fetch_relevant_to_replay_for_player(
        self,
        *,
        player: Player,
        score_id: int,
        map_set_id: int,
        map_id: int,
    ) -> list[CommentWithUserPrivileges]:
        comments = await self.comments.fetch_all_relevant_to_replay(
            score_id=score_id,
            map_set_id=map_set_id,
            map_id=map_id,
        )
        self.schedule_latest_activity_update(player)
        return comments

    async def create_comment_for_player(
        self,
        *,
        player: Player,
        target: str,
        map_set_id: int,
        map_id: int,
        score_id: int,
        start_time: int,
        comment: str,
        colour: str | None,
    ) -> None:
        if colour and not player.priv & Privileges.DONATOR:
            # only supporters can use colours.
            colour = None

            log(
                f"User {player} attempted to use a coloured comment without "
                "supporter status. Submitting comment without a colour.",
            )

        if target == "song":
            target_id = map_set_id
        elif target == "map":
            target_id = map_id
        else:
            target_id = score_id

        await self.comments.create(
            target_id=target_id,
            target_type=TargetType(target),
            userid=player.id,
            time=start_time,
            comment=comment,
            colour=colour,
        )

        self.schedule_latest_activity_update(player)
