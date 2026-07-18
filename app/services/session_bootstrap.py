from __future__ import annotations

from dataclasses import dataclass

from app.constants.privileges import Privileges
from app.logging import Ansi
from app.logging import log
from app.objects.channel import Channel
from app.objects.collections import Channels
from app.objects.collections import Matches
from app.objects.collections import Players
from app.objects.player import Player
from app.repositories.channels import ChannelsRepository
from app.repositories.users import UsersRepository
from app.sessions import SessionState

BOT_USER_ID = 1
BOT_LOGIN_TIME = float(0x7FFFFFFF)  # never auto-disconnect


@dataclass(frozen=True)
class SessionBootstrapService:
    """Construct the isolated in-memory state for one bancho application."""

    channels: ChannelsRepository
    users: UsersRepository

    async def build(self) -> SessionState:
        log("Fetching channels from sql.", Ansi.LCYAN)

        session_channels = Channels()
        for row in await self.channels.fetch_many():
            session_channels.append(
                Channel(
                    name=row.name,
                    topic=row.topic,
                    read_priv=Privileges(row.read_priv),
                    write_priv=Privileges(row.write_priv),
                    auto_join=row.auto_join,
                ),
            )

        bot_user = await self.users.fetch_one(id=BOT_USER_ID)
        if bot_user is None:
            raise RuntimeError("Bot account not found in database.")

        bot = Player(
            id=BOT_USER_ID,
            name=bot_user.name,
            priv=Privileges.UNRESTRICTED,
            pw_bcrypt=None,
            token=Player.generate_token(),
            login_time=BOT_LOGIN_TIME,
            is_bot_client=True,
        )
        players = Players()
        players.append(bot)

        api_keys = {
            record.api_key: record.user_id
            for record in await self.users.fetch_api_keys()
        }

        return SessionState(
            players=players,
            channels=session_channels,
            matches=Matches(),
            bot=bot,
            api_keys=api_keys,
        )
