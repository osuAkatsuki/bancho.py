from __future__ import annotations

from types import SimpleNamespace

import app.services.mail as mail


class _FakeMailRepository:
    def __init__(self) -> None:
        self.read_conversations: list[dict[str, int]] = []

    async def mark_conversation_as_read(self, *, to_id: int, from_id: int) -> None:
        self.read_conversations.append({"to_id": to_id, "from_id": from_id})


class _FakePlayers:
    async def from_cache_or_sql(
        self,
        id: int | None = None,
        name: str | None = None,
    ) -> SimpleNamespace | None:
        return SimpleNamespace(id=8) if name == "Target User" else None


async def test_mail_read_service_marks_decoded_channel_target_as_read() -> None:
    mail_repo = _FakeMailRepository()
    service = mail.MailReadService(mail=mail_repo, players=_FakePlayers())

    await service.mark_channel_as_read(
        player=SimpleNamespace(id=4),
        channel="Target%20User",
    )

    assert mail_repo.read_conversations == [{"to_id": 4, "from_id": 8}]


async def test_mail_read_service_ignores_empty_channel_target() -> None:
    mail_repo = _FakeMailRepository()
    service = mail.MailReadService(mail=mail_repo, players=_FakePlayers())

    await service.mark_channel_as_read(
        player=SimpleNamespace(id=4),
        channel="",
    )

    assert mail_repo.read_conversations == []
