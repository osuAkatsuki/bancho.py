from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import app.packets
from app.logging import Ansi
from app.logging import log
from app.objects.channel import Channel
from app.objects.collections import Channels
from app.objects.collections import Matches
from app.objects.collections import Players
from app.objects.match import Match
from app.objects.match import MatchTeams
from app.objects.match import MatchTeamTypes
from app.objects.match import Slot
from app.objects.match import SlotStatus
from app.objects.player import Player


@dataclass(frozen=True)
class PlayerSessionService:
    """Own mutations spanning players, channels, spectators, and matches."""

    players: Players
    channels: Channels
    matches: Matches
    bot: Player
    decrement_online_players: Callable[[], None]
    debug: bool

    def send_bot(self, player: Player, message: str) -> None:
        player.enqueue(
            app.packets.send_message(
                sender=self.bot.name,
                msg=message,
                recipient=player.name,
                sender_id=self.bot.id,
            ),
        )

    def send_bot_to_channel(self, channel: Channel, message: str) -> None:
        if len(message) >= 31979:
            message = f"message would have crashed games ({len(message)} chars)"

        channel.enqueue(
            app.packets.send_message(
                sender=self.bot.name,
                msg=message,
                recipient=channel.name,
                sender_id=self.bot.id,
            ),
        )

    def join_channel(self, player: Player, channel: Channel) -> bool:
        if (
            player in channel
            or not channel.can_read(player.priv)
            or channel.real_name == "#lobby"
            and not player.in_lobby
        ):
            return False

        channel.append(player)
        player.channels.append(channel)
        player.enqueue(app.packets.channel_join(channel.name))

        channel_info = app.packets.channel_info(
            channel.name,
            channel.topic,
            len(channel.players),
        )
        if channel.instance:
            recipients = channel.players
        else:
            recipients = [
                online_player
                for online_player in self.players
                if channel.can_read(online_player.priv)
            ]

        for recipient in recipients:
            recipient.enqueue(channel_info)

        if self.debug:
            log(f"{player} joined {channel}.")
        return True

    def leave_channel(
        self,
        player: Player,
        channel: Channel,
        *,
        kick: bool = True,
    ) -> None:
        if player not in channel:
            return

        channel.remove(player)
        player.channels.remove(channel)
        if not channel.players and channel.instance and channel in self.channels:
            self.channels.remove(channel)

        if kick:
            player.enqueue(app.packets.channel_kick(channel.name))

        channel_info = app.packets.channel_info(
            channel.name,
            channel.topic,
            len(channel.players),
        )
        if channel.instance:
            recipients = channel.players
        else:
            recipients = [
                online_player
                for online_player in self.players
                if channel.can_read(online_player.priv)
            ]

        for recipient in recipients:
            recipient.enqueue(channel_info)

        if self.debug:
            log(f"{player} left {channel}.")

    def join_match(self, player: Player, match: Match, password: str) -> bool:
        if player.match:
            log(f"{player} tried to join multiple matches?")
            player.enqueue(app.packets.match_join_fail())
            return False

        if player.id in match.tourney_clients:
            player.enqueue(app.packets.match_join_fail())
            return False

        if player.id != match.host_id:
            if password != match.passwd and player not in self.players.staff:
                log(
                    f"{player} tried to join {match} w/ incorrect pw.",
                    Ansi.LYELLOW,
                )
                player.enqueue(app.packets.match_join_fail())
                return False

            slot_id = match.get_free()
            if slot_id is None:
                log(f"{player} tried to join a full match.", Ansi.LYELLOW)
                player.enqueue(app.packets.match_join_fail())
                return False
        else:
            slot_id = 0

        if not self.join_channel(player, match.chat):
            log(f"{player} failed to join {match.chat}.", Ansi.LYELLOW)
            return False

        lobby = self.channels.get_by_name("#lobby")
        if lobby in player.channels:
            assert lobby is not None
            self.leave_channel(player, lobby)

        slot: Slot = match.slots[slot_id]
        if match.team_type in (MatchTeamTypes.team_vs, MatchTeamTypes.tag_team_vs):
            slot.team = MatchTeams.red

        slot.status = SlotStatus.not_ready
        slot.player = player
        player.match = match

        player.enqueue(app.packets.match_join_success(match))
        match.enqueue_state()
        return True

    def leave_match(self, player: Player) -> None:
        match = player.match
        if match is None:
            if self.debug:
                log(f"{player} tried leaving a match they're not in?", Ansi.LYELLOW)
            return

        slot = match.get_slot(player)
        assert slot is not None
        new_status = (
            SlotStatus.locked
            if slot.status == SlotStatus.locked
            else SlotStatus.open
        )
        slot.reset(new_status=new_status)
        self.leave_channel(player, match.chat)

        if all(match_slot.empty() for match_slot in match.slots):
            log(f"Match {match} finished.")
            if match.starting is not None:
                match.starting["start"].cancel()
                for alert in match.starting["alerts"]:
                    alert.cancel()
                match.starting = None

            self.matches.remove(match)
            lobby = self.channels.get_by_name("#lobby")
            if lobby:
                lobby.enqueue(app.packets.dispose_match(match.id))
        else:
            if player.id == match.host_id:
                for match_slot in match.slots:
                    if match_slot.player is not None:
                        match.host_id = match_slot.player.id
                        match_slot.player.enqueue(app.packets.match_transfer_host())
                        break

            if player in match.referees:
                match.referees.remove(player)
                self.send_bot_to_channel(
                    match.chat,
                    f"{player.name} removed from match referees.",
                )
            match.enqueue_state()

        player.match = None

    def add_spectator(self, host: Player, spectator: Player) -> None:
        channel_name = f"#spec_{host.id}"
        channel = self.channels.get_by_name(channel_name)
        if channel is None:
            channel = Channel(
                name=channel_name,
                topic=f"{host.name}'s spectator channel.",
                auto_join=False,
                instance=True,
            )
            self.channels.append(channel)
            self.join_channel(host, channel)

        if not self.join_channel(spectator, channel):
            log(f"{host} failed to join {channel}?", Ansi.LYELLOW)
            return

        if not spectator.stealth:
            joined = app.packets.fellow_spectator_joined(spectator.id)
            for current_spectator in host.spectators:
                current_spectator.enqueue(joined)
                spectator.enqueue(
                    app.packets.fellow_spectator_joined(current_spectator.id),
                )
            host.enqueue(app.packets.spectator_joined(spectator.id))
        else:
            for current_spectator in host.spectators:
                spectator.enqueue(
                    app.packets.fellow_spectator_joined(current_spectator.id),
                )

        host.spectators.append(spectator)
        spectator.spectating = host
        log(f"{spectator} is now spectating {host}.")

    def remove_spectator(self, host: Player, spectator: Player) -> None:
        host.spectators.remove(spectator)
        spectator.spectating = None

        channel = self.channels.get_by_name(f"#spec_{host.id}")
        assert channel is not None
        self.leave_channel(spectator, channel)

        if not host.spectators:
            self.leave_channel(host, channel)
        else:
            channel_info = app.packets.channel_info(
                channel.name,
                channel.topic,
                len(channel.players),
            )
            left = app.packets.fellow_spectator_left(spectator.id)
            host.enqueue(channel_info)
            for current_spectator in host.spectators:
                current_spectator.enqueue(left + channel_info)

        host.enqueue(app.packets.spectator_left(spectator.id))
        log(f"{spectator} is no longer spectating {host}.")

    def logout(self, player: Player) -> None:
        if player.match:
            self.leave_match(player)

        if player.spectating:
            self.remove_spectator(player.spectating, player)

        while player.channels:
            self.leave_channel(player, player.channels[0], kick=False)

        self.players.remove(player)
        player.token = ""

        if not player.restricted:
            self.decrement_online_players()
            self.players.enqueue(app.packets.logout(player.id))

        log(f"{player} logged out.")
