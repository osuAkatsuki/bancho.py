from __future__ import annotations

from types import SimpleNamespace

import app.services.comments as comments
from app.constants.privileges import Privileges
from app.repositories.comments import TargetType


class _FakeCommentsRepository:
    def __init__(self) -> None:
        self.created_comments: list[dict[str, object]] = []

    async def create(self, **comment: object) -> None:
        self.created_comments.append(comment)


async def test_comments_service_strips_colour_for_non_supporter() -> None:
    comments_repo = _FakeCommentsRepository()
    player = SimpleNamespace(
        id=5,
        priv=Privileges.UNRESTRICTED,
        latest_activity_updates=0,
    )
    player.update_latest_activity_soon = lambda: setattr(
        player,
        "latest_activity_updates",
        player.latest_activity_updates + 1,
    )
    service = comments.CommentsService(comments=comments_repo)

    await service.create_comment_for_player(
        player=player,
        target="map",
        map_set_id=100,
        map_id=200,
        score_id=300,
        start_time=1234,
        comment="nice",
        colour="ff00ff",
    )

    assert comments_repo.created_comments == [
        {
            "target_id": 200,
            "target_type": TargetType.BEATMAP,
            "userid": 5,
            "time": 1234,
            "comment": "nice",
            "colour": None,
        },
    ]
    assert player.latest_activity_updates == 1
