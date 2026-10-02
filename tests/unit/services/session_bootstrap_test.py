from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.constants.privileges import Privileges
from app.objects.channel import Channel
from app.repositories.channels import Channel as ChannelRecord
from app.repositories.users import UserApiKey
from app.services.session_bootstrap import BOT_LOGIN_TIME
from app.services.session_bootstrap import BOT_USER_ID
from app.services.session_bootstrap import SessionBootstrapService


class _FakeChannelsRepository:
    def __init__(self) -> None:
        self.fetch_many_calls = 0

    async def fetch_many(self) -> list[ChannelRecord]:
        self.fetch_many_calls += 1
        return [
            ChannelRecord(
                id=1,
                name="#osu",
                topic="General discussion",
                read_priv=int(Privileges.UNRESTRICTED),
                write_priv=int(Privileges.VERIFIED),
                auto_join=True,
            ),
        ]


class _FakeUsersRepository:
    def __init__(self, *, bot_exists: bool = True) -> None:
        self.bot_exists = bot_exists
        self.fetch_one_calls: list[int] = []
        self.fetch_api_keys_calls = 0

    async def fetch_one(self, id: int) -> SimpleNamespace | None:
        self.fetch_one_calls.append(id)
        if not self.bot_exists:
            return None
        return SimpleNamespace(id=id, name="BanchoBot")

    async def fetch_api_keys(self) -> list[UserApiKey]:
        self.fetch_api_keys_calls += 1
        return [
            UserApiKey(user_id=3, api_key="first-key"),
            UserApiKey(user_id=4, api_key="second-key"),
        ]


async def test_session_bootstrap_loads_channels_bot_and_api_keys() -> None:
    channels = _FakeChannelsRepository()
    users = _FakeUsersRepository()
    service = SessionBootstrapService(channels=channels, users=users)

    sessions = await service.build()

    osu_channel = sessions.channels.get_by_name("#osu")
    assert osu_channel is not None
    assert osu_channel.topic == "General discussion"
    assert osu_channel.read_priv is Privileges.UNRESTRICTED
    assert osu_channel.write_priv is Privileges.VERIFIED
    assert osu_channel.auto_join is True

    assert sessions.bot.id == BOT_USER_ID
    assert sessions.bot.name == "BanchoBot"
    assert sessions.bot.login_time == BOT_LOGIN_TIME
    assert sessions.bot.is_bot_client is True
    assert sessions.players.get(id=BOT_USER_ID) is sessions.bot

    assert sessions.api_keys == {"first-key": 3, "second-key": 4}
    assert len(sessions.matches) == 64
    assert all(match is None for match in sessions.matches)
    assert channels.fetch_many_calls == 1
    assert users.fetch_one_calls == [BOT_USER_ID]
    assert users.fetch_api_keys_calls == 1


async def test_session_bootstrap_builds_isolated_state_each_time() -> None:
    service = SessionBootstrapService(
        channels=_FakeChannelsRepository(),
        users=_FakeUsersRepository(),
    )

    first = await service.build()
    second = await service.build()

    first.channels.append(Channel("#first-only", "isolated"))
    first.api_keys["first-only"] = 5

    assert second.channels.get_by_name("#first-only") is None
    assert "first-only" not in second.api_keys
    assert first.players is not second.players
    assert first.channels is not second.channels
    assert first.matches is not second.matches
    assert first.bot is not second.bot


async def test_session_bootstrap_requires_the_bot_account() -> None:
    users = _FakeUsersRepository(bot_exists=False)
    service = SessionBootstrapService(
        channels=_FakeChannelsRepository(),
        users=users,
    )

    with pytest.raises(RuntimeError, match="Bot account not found"):
        await service.build()

    assert users.fetch_api_keys_calls == 0
