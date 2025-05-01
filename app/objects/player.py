from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from datetime import date
from enum import IntEnum
from enum import StrEnum
from enum import unique
from functools import cached_property
from typing import TYPE_CHECKING
from typing import TypedDict
from typing import cast

import databases.core

import app.packets
import app.settings
import app.state
from app._typing import IPAddress
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.constants.privileges import ClientPrivileges
from app.constants.privileges import Privileges
from app.discord import Webhook
from app.logging import Ansi
from app.logging import log
from app.objects.channel import Channel
from app.objects.match import Match
from app.objects.match import MatchTeams
from app.objects.match import MatchTeamTypes
from app.objects.match import Slot
from app.objects.match import SlotStatus
from app.objects.score import Grade
from app.objects.score import Score
from app.repositories import clans as clans_repo
from app.repositories import logs as logs_repo
from app.repositories import stats as stats_repo
from app.repositories import users as users_repo
from app.state.services import Geolocation
from app.utils import escape_enum
from app.utils import make_safe_name
from app.utils import pymysql_encode

if TYPE_CHECKING:
    from app.constants.privileges import ClanPrivileges
    from app.objects.beatmap import Beatmap
    from app.objects.score import Score


@unique
@pymysql_encode(escape_enum)
class PresenceFilter(IntEnum):
    """osu! client side filter for which users the player can see."""

    Nil = 0
    All = 1
    Friends = 2


@unique
@pymysql_encode(escape_enum)
class Action(IntEnum):
    """The client's current app.state."""

    Idle = 0
    Afk = 1
    Playing = 2
    Editing = 3
    Modding = 4
    Multiplayer = 5
    Watching = 6
    Unknown = 7
    Testing = 8
    Submitting = 9
    Paused = 10
    Lobby = 11
    Multiplaying = 12
    OsuDirect = 13


@dataclass
class ModeData:
    """A player's stats in a single gamemode."""

    tscore: int
    rscore: int
    pp: int
    acc: float
    plays: int
    playtime: int
    max_combo: int
    total_hits: int
    rank: int  # global

    grades: dict[Grade, int]  # XH, X, SH, S, A


@dataclass
class Status:
    """The current status of a player."""

    action: Action = Action.Idle
    info_text: str = ""
    map_md5: str = ""
    mods: Mods = Mods.NOMOD
    mode: GameMode = GameMode.VANILLA_OSU
    map_id: int = 0


class LastNp(TypedDict):
    bmap: Beatmap
    mode_vn: int
    mods: Mods | None
    timeout: float


class OsuStream(StrEnum):
    STABLE = "stable"
    BETA = "beta"
    CUTTINGEDGE = "cuttingedge"
    TOURNEY = "tourney"
    DEV = "dev"


class OsuVersion:
    # b20200201.2cuttingedge
    # date = 2020/02/01
    # revision = 2
    # stream = cuttingedge
    def __init__(
        self,
        date: date,
        revision: int | None,  # TODO: should this be optional?
        stream: OsuStream,
    ) -> None:
        self.date = date
        self.revision = revision
        self.stream = stream


class ClientDetails:
    def __init__(
        self,
        osu_version: OsuVersion,
        osu_path_md5: str,
        adapters_md5: str,
        uninstall_md5: str,
        disk_signature_md5: str,
        adapters: list[str],
        ip: IPAddress,
    ) -> None:
        self.osu_version = osu_version
        self.osu_path_md5 = osu_path_md5
        self.adapters_md5 = adapters_md5
        self.uninstall_md5 = uninstall_md5
        self.disk_signature_md5 = disk_signature_md5

        self.adapters = adapters
        self.ip = ip

    @cached_property
    def client_hash(self) -> str:
        return (
            # NOTE the extra '.' and ':' appended to ends
            f"{self.osu_path_md5}:{'.'.join(self.adapters)}."
            f":{self.adapters_md5}:{self.uninstall_md5}:{self.disk_signature_md5}:"
        )

    # TODO: __str__ to pack like osu! hashes?


class Player:
    """\
    Server side representation of a player; not necessarily online.

    Possibly confusing attributes
    -----------
    token: `str`
        The player's unique token; used to
        communicate with the osu! client.

    safe_name: `str`
        The player's username (safe).
        XXX: Equivalent to `cls.name.lower().replace(' ', '_')`.

    pm_private: `bool`
        Whether the player is blocking pms from non-friends.

    silence_end: `int`
        The UNIX timestamp the player's silence will end at.

    pres_filter: `PresenceFilter`
        The scope of users the client can currently see.

    is_bot_client: `bool`
        Whether this is a bot account.

    is_tourney_client: `bool`
        Whether this is a management/spectator tourney client.

    _packet_queue: `bytearray`
        Bytes enqueued to the player which will be transmitted
        at the tail end of their next connection to the server.
        XXX: cls.enqueue() will add data to this queue, and
             cls.dequeue() will return the data, and remove it.
    """

    def __init__(
        self,
        id: int,
        name: str,
        priv: Privileges,
        pw_bcrypt: bytes | None,
        token: str,
        clan_id: int | None = None,
        clan_priv: ClanPrivileges | None = None,
        geoloc: Geolocation | None = None,
        utc_offset: int = 0,
        pm_private: bool = False,
        silence_end: int = 0,
        donor_end: int = 0,
        client_details: ClientDetails | None = None,
        login_time: float = 0.0,
        is_bot_client: bool = False,
        is_tourney_client: bool = False,
        api_key: str | None = None,
    ) -> None:
        if geoloc is None:
            geoloc = {
                "latitude": 0.0,
                "longitude": 0.0,
                "country": {"acronym": "xx", "numeric": 0},
            }

        self.id = id
        self.name = name
        self.priv = priv
        self.pw_bcrypt = pw_bcrypt
        self.token = token
        self.clan_id = clan_id
        self.clan_priv = clan_priv
        self.geoloc = geoloc
        self.utc_offset = utc_offset
        self.pm_private = pm_private
        self.silence_end = silence_end
        self.donor_end = donor_end
        self.client_details = client_details
        self.login_time = login_time
        self.last_recv_time = login_time
        self.is_bot_client = is_bot_client
        self.is_tourney_client = is_tourney_client
        self.api_key = api_key

        # avoid enqueuing packets to bot accounts.
        if self.is_bot_client:

            def _noop_enqueue(data: bytes) -> None:
                pass

            self.enqueue = _noop_enqueue  # type: ignore[method-assign]

        self.away_msg: str | None = None
        self.in_lobby = False

        self.stats: dict[GameMode, ModeData] = {}
        self.status = Status()

        # userids, not player objects
        self.friends: set[int] = set()
        self.blocks: set[int] = set()

        self.channels: list[Channel] = []
        self.spectators: list[Player] = []
        self.spectating: Player | None = None
        self.match: Match | None = None
        self.stealth = False

        self.pres_filter = PresenceFilter.Nil

        # store most recent score for each gamemode.
        self.recent_scores: dict[GameMode, Score | None] = {
            mode: None for mode in GameMode
        }

        # store the last beatmap /np'ed by the user.
        self.last_np: LastNp | None = None

        self._packet_queue = bytearray()

    def __repr__(self) -> str:
        return f"<{self.name} ({self.id})>"

    @property
    def safe_name(self) -> str:
        return make_safe_name(self.name)

    @property
    def is_online(self) -> bool:
        return bool(self.token != "")

    @property
    def url(self) -> str:
        """The url to the player's profile."""
        return f"https://{app.settings.DOMAIN}/u/{self.id}"

    @property
    def embed(self) -> str:
        """An osu! chat embed to the player's profile."""
        return f"[{self.url} {self.name}]"

    @property
    def avatar_url(self) -> str:
        """The url to the player's avatar."""
        return f"https://a.{app.settings.DOMAIN}/{self.id}"

    # TODO: chat embed with clan tag hyperlinked?

    @property
    def remaining_silence(self) -> int:
        """The remaining time of the players silence."""
        return max(0, int(self.silence_end - time.time()))

    @property
    def silenced(self) -> bool:
        """Whether or not the player is silenced."""
        return self.remaining_silence != 0

    @cached_property
    def bancho_priv(self) -> ClientPrivileges:
        """The player's privileges according to the client."""
        ret = ClientPrivileges(0)
        if self.priv & Privileges.UNRESTRICTED:
            ret |= ClientPrivileges.PLAYER
        if self.priv & Privileges.DONATOR:
            ret |= ClientPrivileges.SUPPORTER
        if self.priv & Privileges.MODERATOR:
            ret |= ClientPrivileges.MODERATOR
        if self.priv & Privileges.ADMINISTRATOR:
            ret |= ClientPrivileges.DEVELOPER
        if self.priv & Privileges.DEVELOPER:
            ret |= ClientPrivileges.OWNER
        return ret

    @property
    def restricted(self) -> bool:
        """Return whether the player is restricted."""
        return not self.priv & Privileges.UNRESTRICTED

    @property
    def gm_stats(self) -> ModeData:
        """The player's stats in their currently selected mode."""
        return self.stats[self.status.mode]

    @property
    def recent_score(self) -> Score | None:
        """The player's most recently submitted score."""
        score = None
        for s in self.recent_scores.values():
            if not s:
                continue

            if not score:
                score = s
                continue

            if s.server_time > score.server_time:
                score = s

        return score

    @staticmethod
    def generate_token() -> str:
        """Generate a random uuid as a token."""
        return str(uuid.uuid4())

    def logout(self) -> None:
        """Log `self` out of the server."""
        # invalidate the user's token.
        self.token = ""

        # leave multiplayer.
        if self.match:
            self.leave_match()

        # stop spectating.
        host = self.spectating
        if host:
            host.remove_spectator(self)

        # leave channels
        while self.channels:
            self.leave_channel(self.channels[0], kick=False)

        # remove from playerlist and
        # enqueue logout to all users.
        app.state.sessions.players.remove(self)

        if not self.restricted:
            if app.state.services.datadog:
                app.state.services.datadog.decrement("bancho.online_players")  # type: ignore[no-untyped-call]

            app.state.sessions.players.enqueue(app.packets.logout(self.id))

        log(f"{self} logged out.")

    async def update_privs(self, new: Privileges) -> None:
        """Update `self`'s privileges to `new`."""

        self.priv = new
        if "bancho_priv" in vars(self):
            del self.bancho_priv  # wipe cached_property

        await users_repo.partial_update(
            id=self.id,
            priv=self.priv,
        )

    async def add_privs(self, bits: Privileges) -> None:
        """Update `self`'s privileges, adding `bits`."""

        self.priv |= bits
        if "bancho_priv" in vars(self):
            del self.bancho_priv  # wipe cached_property

        await users_repo.partial_update(
            id=self.id,
            priv=self.priv,
        )

        if self.is_online:
            # if they're online, send a packet
            # to update their client-side privileges
            self.enqueue(app.packets.bancho_privileges(self.bancho_priv))

    async def remove_privs(self, bits: Privileges) -> None:
        """Update `self`'s privileges, removing `bits`."""

        self.priv &= ~bits
        if "bancho_priv" in vars(self):
            del self.bancho_priv  # wipe cached_property

        await users_repo.partial_update(
            id=self.id,
            priv=self.priv,
        )

        if self.is_online:
            # if they're online, send a packet
            # to update their client-side privileges
            self.enqueue(app.packets.bancho_privileges(self.bancho_priv))

    async def restrict(self, admin: Player, reason: str) -> None:
        """Restrict `self` for `reason`, and log to sql."""
        await self.remove_privs(Privileges.UNRESTRICTED)

        await logs_repo.create(
            _from=admin.id,
            to=self.id,
            action="restrict",
            msg=reason,
        )

        for mode in (0, 1, 2, 3, 4, 5, 6, 8):
            await app.state.services.redis.zrem(
                f"bancho:leaderboard:{mode}",
                self.id,
            )
            await app.state.services.redis.zrem(
                f'bancho:leaderboard:{mode}:{self.geoloc["country"]["acronym"]}',
                self.id,
            )

        log_msg = f"{admin} restricted {self} for: {reason}."

        log(log_msg, Ansi.LRED)

        webhook_url = app.settings.DISCORD_AUDIT_LOG_WEBHOOK
        if webhook_url:
            webhook = Webhook(webhook_url, content=log_msg)
            asyncio.create_task(webhook.post())  # type: ignore[unused-awaitable]

        # refresh their client state
        if self.is_online:
            self.logout()

    async def unrestrict(self, admin: Player, reason: str) -> None:
        """Restrict `self` for `reason`, and log to sql."""
        await self.add_privs(Privileges.UNRESTRICTED)

        await logs_repo.create(
            _from=admin.id,
            to=self.id,
            action="unrestrict",
            msg=reason,
        )

        if not self.is_online:
            await self.stats_from_sql_full()

        for mode, stats in self.stats.items():
            await app.state.services.redis.zadd(
                f"bancho:leaderboard:{mode.value}",
                {str(self.id): stats.pp},
            )
            await app.state.services.redis.zadd(
                f"bancho:leaderboard:{mode.value}:{self.geoloc['country']['acronym']}",
                {str(self.id): stats.pp},
            )

        log_msg = f"{admin} unrestricted {self} for: {reason}."

        log(log_msg, Ansi.LRED)

        webhook_url = app.settings.DISCORD_AUDIT_LOG_WEBHOOK
        if webhook_url:
            webhook = Webhook(webhook_url, content=log_msg)
            asyncio.create_task(webhook.post())  # type: ignore[unused-awaitable]

        if self.is_online:
            # log the user out if they're offline, this
            # will simply relog them and refresh their app.state
            self.logout()

    async def silence(self, admin: Player, duration: float, reason: str) -> None:
        """Silence `self` for `duration` seconds, and log to sql."""
        self.silence_end = int(time.time() + duration)

        await users_repo.partial_update(
            id=self.id,
            silence_end=self.silence_end,
        )

        await logs_repo.create(
            _from=admin.id,
            to=self.id,
            action="silence",
            msg=reason,
        )

        # inform the user's client.
        self.enqueue(app.packets.silence_end(int(duration)))

        # wipe their messages from any channels.
        app.state.sessions.players.enqueue(app.packets.user_silenced(self.id))

        # remove them from multiplayer match (if any).
        if self.match:
            self.leave_match()

        log(f"Silenced {self}.", Ansi.LCYAN)

    async def unsilence(self, admin: Player, reason: str) -> None:
        """Unsilence `self`, and log to sql."""
        self.silence_end = int(time.time())

        await users_repo.partial_update(
            id=self.id,
            silence_end=self.silence_end,
        )

        await logs_repo.create(
            _from=admin.id,
            to=self.id,
            action="unsilence",
            msg=reason,
        )

        # inform the user's client
        self.enqueue(app.packets.silence_end(0))

        log(f"Unsilenced {self}.", Ansi.LCYAN)

    def join_match(self, match: Match, passwd: str) -> bool:
        """Attempt to add `self` to `match`."""
        if self.match:
            log(f"{self} tried to join multiple matches?")
            self.enqueue(app.packets.match_join_fail())
            return False

        if self.id in match.tourney_clients:
            # the user is already in the match with a tourney client.
            # users cannot spectate themselves so this is not possible.
            self.enqueue(app.packets.match_join_fail())
            return False

        if self is not match.host:
            # match already exists, we're simply joining.
            # NOTE: staff members have override to pw and can
            # simply use any to join a pw protected match.
            if passwd != match.passwd and self not in app.state.sessions.players.staff:
                log(f"{self} tried to join {match} w/ incorrect pw.", Ansi.LYELLOW)
                self.enqueue(app.packets.match_join_fail())
                return False
            slot_id = match.get_free()
            if slot_id is None:
                log(f"{self} tried to join a full match.", Ansi.LYELLOW)
                self.enqueue(app.packets.match_join_fail())
                return False

        else:
            # match is being created
            slot_id = 0

        if not self.join_channel(match.chat):
            log(f"{self} failed to join {match.chat}.", Ansi.LYELLOW)
            return False

        lobby = app.state.sessions.channels.get_by_name("#lobby")
        if lobby in self.channels:
            self.leave_channel(lobby)

        slot: Slot = match.slots[0 if slot_id == -1 else slot_id]

        # if in a teams-vs mode, switch team from neutral to red.
        if match.team_type in (MatchTeamTypes.team_vs, MatchTeamTypes.tag_team_vs):
            slot.team = MatchTeams.red

        slot.status = SlotStatus.not_ready
        slot.player = self
        self.match = match

        self.enqueue(app.packets.match_join_success(match))
        match.enqueue_state()

        return True

    def leave_match(self) -> None:
        """Attempt to remove `self` from their match."""
        if not self.match:
            if app.settings.DEBUG:
                log(f"{self} tried leaving a match they're not in?", Ansi.LYELLOW)
            return

        slot = self.match.get_slot(self)
        assert slot is not None

        if slot.status == SlotStatus.locked:
            # player was kicked, keep the slot locked.
            new_status = SlotStatus.locked
        else:
            # player left, open the slot for new players to join.
            new_status = SlotStatus.open

        slot.reset(new_status=new_status)

        self.leave_channel(self.match.chat)

        if all(s.empty() for s in self.match.slots):
            # multi is now empty, chat has been removed.
            # remove the multi from the channels list.
            log(f"Match {self.match} finished.")

            # cancel any pending start timers
            if self.match.starting is not None:
                self.match.starting["start"].cancel()
                for alert in self.match.starting["alerts"]:
                    alert.cancel()

                self.match.starting = None

            app.state.sessions.matches.remove(self.match)

            lobby = app.state.sessions.channels.get_by_name("#lobby")
            if lobby:
                lobby.enqueue(app.packets.dispose_match(self.match.id))

        else:  # multi is not empty
            if self is self.match.host:
                # player was host, trasnfer to first occupied slot
                for s in self.match.slots:
                    if s.player is not None:
                        self.match.host_id = s.player.id
                        self.match.host.enqueue(app.packets.match_transfer_host())
                        break

            if self in self.match.referees:
                self.match.referees.remove(self)
                self.match.chat.send_bot(f"{self.name} removed from match referees.")

            # notify others of our deprature
            self.match.enqueue_state()

        self.match = None

    def join_channel(self, channel: Channel) -> bool:
        """Attempt to add `self` to `channel`."""
        if (
            self in channel
            or not channel.can_read(self.priv)  # player already in channel
            or channel.real_name == "#lobby"  # no read privs
            and not self.in_lobby  # not in mp lobby
        ):
            return False

        channel.append(self)  # add to channel.players
        self.channels.append(channel)  # add to player.channels

        self.enqueue(app.packets.channel_join(channel.name))

        chan_info_packet = app.packets.channel_info(
            channel.name,
            channel.topic,
            len(channel.players),
        )

        if channel.instance:
            # instanced channel, only send the players
            # who are currently inside the instance
            for player in channel.players:
                player.enqueue(chan_info_packet)
        else:
            # normal channel, send to all players who
            # have access to see the channel's usercount.
            for player in app.state.sessions.players:
                if channel.can_read(player.priv):
                    player.enqueue(chan_info_packet)

        if app.settings.DEBUG:
            log(f"{self} joined {channel}.")

        return True

    def leave_channel(self, channel: Channel, kick: bool = True) -> None:
        """Attempt to remove `self` from `channel`."""
        # ensure they're in the chan.
        if self not in channel:
            return

        channel.remove(self)  # remove from c.players
        self.channels.remove(channel)  # remove from player.channels

        if kick:
            self.enqueue(app.packets.channel_kick(channel.name))

        chan_info_packet = app.packets.channel_info(
            channel.name,
            channel.topic,
            len(channel.players),
        )

        if channel.instance:
            # instanced channel, only send the players
            # who are currently inside the instance
            for player in channel.players:
                player.enqueue(chan_info_packet)
        else:
            # normal channel, send to all players who
            # have access to see the channel's usercount.
            for player in app.state.sessions.players:
                if channel.can_read(player.priv):
                    player.enqueue(chan_info_packet)

        if app.settings.DEBUG:
            log(f"{self} left {channel}.")

    def add_spectator(self, player: Player) -> None:
        """Attempt to add `player` to `self`'s spectators."""
        chan_name = f"#spec_{self.id}"

        spec_chan = app.state.sessions.channels.get_by_name(chan_name)
        if not spec_chan:
            # spectator chan doesn't exist, create it.
            spec_chan = Channel(
                name=chan_name,
                topic=f"{self.name}'s spectator channel.",
                auto_join=False,
                instance=True,
            )

            self.join_channel(spec_chan)
            app.state.sessions.channels.append(spec_chan)

        # attempt to join their spectator channel.
        if not player.join_channel(spec_chan):
            log(f"{self} failed to join {spec_chan}?", Ansi.LYELLOW)
            return

        if not player.stealth:
            player_joined = app.packets.fellow_spectator_joined(player.id)
            for spectator in self.spectators:
                spectator.enqueue(player_joined)
                player.enqueue(app.packets.fellow_spectator_joined(spectator.id))

            self.enqueue(app.packets.spectator_joined(player.id))
        else:
            # player is admin in stealth, only give
            # other players data to us, not vice-versa.
            for spectator in self.spectators:
                player.enqueue(app.packets.fellow_spectator_joined(spectator.id))

        self.spectators.append(player)
        player.spectating = self

        log(f"{player} is now spectating {self}.")

    def remove_spectator(self, player: Player) -> None:
        """Attempt to remove `player` from `self`'s spectators."""
        self.spectators.remove(player)
        player.spectating = None

        channel = app.state.sessions.channels.get_by_name(f"#spec_{self.id}")
        assert channel is not None

        player.leave_channel(channel)

        if not self.spectators:
            # remove host from channel, deleting it.
            self.leave_channel(channel)
        else:
            # send new playercount
            channel_info = app.packets.channel_info(
                channel.name,
                channel.topic,
                len(channel.players),
            )
            fellow = app.packets.fellow_spectator_left(player.id)

            self.enqueue(channel_info)

            for spectator in self.spectators:
                spectator.enqueue(fellow + channel_info)

        self.enqueue(app.packets.spectator_left(player.id))
        log(f"{player} is no longer spectating {self}.")

    async def add_friend(self, player: Player) -> None:
        """Attempt to add `player` to `self`'s friends."""
        if player.id in self.friends:
            log(
                f"{self} tried to add {player}, who is already their friend!",
                Ansi.LYELLOW,
            )
            return

        self.friends.add(player.id)
        await app.state.services.database.execute(
            "REPLACE INTO relationships (user1, user2, type) VALUES (:user1, :user2, 'friend')",
            {"user1": self.id, "user2": player.id},
        )

        log(f"{self} friended {player}.")

    async def remove_friend(self, player: Player) -> None:
        """Attempt to remove `player` from `self`'s friends."""
        if player.id not in self.friends:
            log(
                f"{self} tried to unfriend {player}, who is not their friend!",
                Ansi.LYELLOW,
            )
            return

        self.friends.remove(player.id)
        await app.state.services.database.execute(
            "DELETE FROM relationships WHERE user1 = :user1 AND user2 = :user2",
            {"user1": self.id, "user2": player.id},
        )

        log(f"{self} unfriended {player}.")

    async def add_block(self, player: Player) -> None:
        """Attempt to add `player` to `self`'s blocks."""
        if player.id in self.blocks:
            log(
                f"{self} tried to block {player}, who they've already blocked!",
                Ansi.LYELLOW,
            )
            return

        self.blocks.add(player.id)
        await app.state.services.database.execute(
            "REPLACE INTO relationships VALUES (:user1, :user2, 'block')",
            {"user1": self.id, "user2": player.id},
        )

        log(f"{self} blocked {player}.")

    async def remove_block(self, player: Player) -> None:
        """Attempt to remove `player` from `self`'s blocks."""
        if player.id not in self.blocks:
            log(
                f"{self} tried to unblock {player}, who they haven't blocked!",
                Ansi.LYELLOW,
            )
            return

        self.blocks.remove(player.id)
        await app.state.services.database.execute(
            "DELETE FROM relationships WHERE user1 = :user1 AND user2 = :user2",
            {"user1": self.id, "user2": player.id},
        )

        log(f"{self} unblocked {player}.")

    async def relationships_from_sql(self) -> None:
        """Retrieve `self`'s relationships from sql."""
        for row in await app.state.services.database.fetch_all(
            "SELECT user2, type FROM relationships WHERE user1 = :user1",
            {"user1": self.id},
        ):
            if row["type"] == "friend":
                self.friends.add(row["user2"])
            else:
                self.blocks.add(row["user2"])

        # always have bot added to friends.
        self.friends.add(1)

    async def get_global_rank(self, mode: GameMode) -> int:
        if self.restricted:
            return 0

        rank = await app.state.services.redis.zrevrank(
            f"bancho:leaderboard:{mode.value}",
            str(self.id),
        )
        return cast(int, rank) + 1 if rank is not None else 0

    async def get_country_rank(self, mode: GameMode) -> int:
        if self.restricted:
            return 0

        country = self.geoloc["country"]["acronym"]
        rank = await app.state.services.redis.zrevrank(
            f"bancho:leaderboard:{mode.value}:{country}",
            str(self.id),
        )

        return cast(int, rank) + 1 if rank is not None else 0

    async def update_rank(self, mode: GameMode) -> int:
        country = self.geoloc["country"]["acronym"]
        stats = self.stats[mode]

        if not self.restricted:
            # global rank
            await app.state.services.redis.zadd(
                f"bancho:leaderboard:{mode.value}",
                {str(self.id): stats.pp},
            )

            # country rank
            await app.state.services.redis.zadd(
                f"bancho:leaderboard:{mode.value}:{country}",
                {str(self.id): stats.pp},
            )

        return await self.get_global_rank(mode)

    async def stats_from_sql_full(self) -> None:
        """Retrieve `self`'s stats (all modes) from sql."""
        for row in await stats_repo.fetch_many(player_id=self.id):
            game_mode = GameMode(row["mode"])
            self.stats[game_mode] = ModeData(
                tscore=row["tscore"],
                rscore=row["rscore"],
                pp=row["pp"],
                acc=row["acc"],
                plays=row["plays"],
                playtime=row["playtime"],
                max_combo=row["max_combo"],
                total_hits=row["total_hits"],
                rank=await self.get_global_rank(game_mode),
                grades={
                    Grade.XH: row["xh_count"],
                    Grade.X: row["x_count"],
                    Grade.SH: row["sh_count"],
                    Grade.S: row["s_count"],
                    Grade.A: row["a_count"],
                },
            )

    def update_latest_activity_soon(self) -> None:
        """Update the player's latest activity in the database."""
        task = users_repo.partial_update(
            id=self.id,
            latest_activity=int(time.time()),
        )
        app.state.loop.create_task(task)  # type: ignore[unused-awaitable]

    def enqueue(self, data: bytes) -> None:
        """Add data to be sent to the client."""
        self._packet_queue += data

    def dequeue(self) -> bytes | None:
        """Get data from the queue to send to the client."""
        if self._packet_queue:
            data = bytes(self._packet_queue)
            self._packet_queue.clear()
            return data

        return None

    def send(self, msg: str, sender: Player, chan: Channel | None = None) -> None:
        """Enqueue `sender`'s `msg` to `self`. Sent in `chan`, or dm."""
        self.enqueue(
            app.packets.send_message(
                sender=sender.name,
                msg=msg,
                recipient=(chan or self).name,
                sender_id=sender.id,
            ),
        )

    def send_bot(self, msg: str) -> None:
        """Enqueue `msg` to `self` from bot."""
        bot = app.state.sessions.bot

        self.enqueue(
            app.packets.send_message(
                sender=bot.name,
                msg=msg,
                recipient=self.name,
                sender_id=bot.id,
            ),
        )
