from __future__ import annotations

from typing import Sequence

import app.packets
import app.repositories.channels
import app.state.sessions
from app.objects.channel import Channel
from app.objects.player import Player


def can_read(channel: Channel, priv: int) -> bool:
    """Check whether a set of privs are able to read from a channel."""
    if not channel.read_priv:
        return True

    return priv & channel.read_priv != 0


def can_write(channel: Channel, priv: int) -> bool:
    """Check whether a set of privs are able to write to a channel."""
    if not channel.write_priv:
        return True

    return priv & channel.write_priv != 0


def send_data_to_clients(
    channel: Channel,
    data: bytes,
    immune: Sequence[int] = [],
) -> None:
    """Enqueue arbitrary data to all clients not in in the immune list."""
    for player in channel.players:
        if player.id not in immune:
            player.enqueue(data)


def send_msg_to_clients(
    channel: Channel,
    msg: str,
    sender: Player,
    to_self: bool = False,
) -> None:
    """Enqueue a sender's message to all clients."""
    data = app.packets.send_message(
        sender=sender.name,
        msg=msg,
        recipient=channel.name,
        sender_id=sender.id,
    )

    for player in channel.players:
        if sender.id not in player.blocks and (to_self or player.id != sender.id):
            player.enqueue(data)


def send_bot(channel: Channel, msg: str) -> None:
    """Enqueue a message to all clients from the bot."""
    bot = app.state.sessions.bot

    if len(msg) >= 31979:  # TODO ??????????
        msg = f"message would have crashed games ({len(msg)} chars)"

    send_data_to_clients(
        channel,
        app.packets.send_message(
            sender=bot.name,
            msg=msg,
            recipient=channel.name,
            sender_id=bot.id,
        ),
    )


def send_selective(
    channel: Channel,
    msg: str,
    sender: Player,
    recipients: set[Player],
) -> None:
    """Enqueue a sender's message to a set of recipients in a given channel."""
    for p in recipients:
        if p in channel:
            send_data_to_clients(
                channel,
                app.packets.send_message(
                    sender=sender.name,
                    msg=msg,
                    recipient=channel.name,
                    sender_id=sender.id,
                ),
            )


def join_channel(channel: Channel, player: Player) -> None:
    """Add a player to a channel."""
    channel.players.append(player)


def remove_channel(channel: Channel, player: Player) -> None:
    """Remove a player from a channel."""
    channel.players.remove(player)

    if channel.instance and not channel.players:
        # delete instanced channels once all players have left
        app.repositories.channels.delete_instance(channel.name)
        app.state.sessions.channels.remove(channel)
