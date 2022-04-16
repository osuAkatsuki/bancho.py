from __future__ import annotations

import hashlib
import time
import uuid
from typing import Mapping
from typing import Optional
from typing import TYPE_CHECKING

import bcrypt

import app.packets
import app.repositories.players
import app.settings
import app.state
import app.usecases.channels
import app.usecases.clans
import app.usecases.multiplayer
from app.constants.gamemodes import GameMode
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
from app.objects.player import ModeData
from app.objects.score import Grade

if TYPE_CHECKING:
    from app.objects.achievement import Achievement
    from app.objects.player import Player

# TODO: organize this

# utils


# TODO: not really sure this should be here
def validate_credentials(password: bytes, hashed_password: bytes) -> bool:
    """Validate a password against a hashed password."""
    if cached_password := app.state.cache.bcrypt.get(hashed_password):
        return password == cached_password
    else:
        if result := bcrypt.checkpw(password, hashed_password):
            app.state.cache.bcrypt[hashed_password] = password

        return result


# usecases


def generate_token() -> str:
    """Generate a random uuid as a token."""
    return str(uuid.uuid4())


# if token is not None:
#     player.token = token
# else:
#     player.token = player.generate_token()


# TODO: enqueue_to_all, enqueue_to_player, dequeue?


async def register(
    player_name: str,
    email: str,
    pw_plaintext: str,
    country: str,
) -> int:
    """Register a user in our database, returning their new id."""
    pw_md5 = hashlib.md5(pw_plaintext.encode()).hexdigest().encode()
    pw_bcrypt = bcrypt.hashpw(pw_md5, bcrypt.gensalt())
    app.state.cache.bcrypt[pw_bcrypt] = pw_md5  # cache result for login

    async with app.state.services.database.connection() as db_conn:
        # add to `users` table.
        user_id = await db_conn.execute(
            "INSERT INTO users "
            "(name, safe_name, email, pw_bcrypt, country, creation_time, latest_activity) "
            "VALUES (:name, :safe_name, :email, :pw_bcrypt, :country, UNIX_TIMESTAMP(), UNIX_TIMESTAMP())",
            {
                "name": player_name,
                "safe_name": player_name.lower().replace(" ", "_"),
                "email": email,
                "pw_bcrypt": pw_bcrypt,
                "country": country,
            },
        )

        # add to `stats` table.
        await db_conn.execute_many(
            "INSERT INTO stats (id, mode) VALUES (:user_id, :mode)",
            [
                {"user_id": user_id, "mode": mode}
                for mode in (
                    0,  # vn!std
                    1,  # vn!taiko
                    2,  # vn!catch
                    3,  # vn!mania
                    4,  # rx!std
                    5,  # rx!taiko
                    6,  # rx!catch
                    8,  # ap!std
                )
            ],
        )

    return user_id


async def login(player_name: str, player_password_md5: bytes) -> Optional[Player]:
    player = await app.repositories.players.fetch(player_name=player_name)

    if player and validate_credentials(
        password=player_password_md5,
        hashed_password=player.pw_bcrypt,  # type: ignore
    ):
        return player


def logout(player: Player) -> None:
    """Log `player` out of the server."""
    # invalidate the user's token.
    player.token = ""

    # leave multiplayer.
    if player.match:
        leave_match(player)

    # stop spectating.
    if host := player.spectating:
        remove_spectator(host, player)

    # leave channels
    for channel in reversed(player.channels):
        leave_channel(player, channel, kick=False)

    # remove from playerlist and
    # enqueue logout to all users.
    app.state.sessions.players.remove(player)

    if not player.restricted:
        if app.state.services.datadog:
            app.state.services.datadog.decrement("bancho.online_players")

        app.state.sessions.players.enqueue(app.packets.logout(player.id))

    log(f"{player} logged out.", Ansi.LYELLOW)


async def update_privs(player: Player, new_privs: int) -> None:
    """Update a player's privileges to a new value."""
    player.priv = new_privs

    await app.state.services.database.execute(
        "UPDATE users SET priv = :priv WHERE id = :user_id",
        {"priv": player.priv, "user_id": player.id},
    )


async def add_privs(player: Player, bits: int) -> None:
    """Update a player's privileges, adding some bits."""
    player.priv |= bits

    await app.state.services.database.execute(
        "UPDATE users SET priv = :priv WHERE id = :user_id",
        {"priv": player.priv, "user_id": player.id},
    )

    if player.online:
        # if they're online, send a packet
        # to update their client-side privileges
        player.enqueue(app.packets.bancho_privileges(player.bancho_priv))


async def remove_privs(player: Player, bits: int) -> None:
    """Update a player's privileges, removing some bits."""
    player.priv &= ~bits

    await app.state.services.database.execute(
        "UPDATE users SET priv = :priv WHERE id = :user_id",
        {"priv": player.priv, "user_id": player.id},
    )

    if player.online:
        # if they're online, send a packet
        # to update their client-side privileges
        player.enqueue(app.packets.bancho_privileges(player.bancho_priv))


async def restrict(player: Player, admin: Player, reason: str) -> None:
    """Restrict a player with a reason, and log to sql."""
    await remove_privs(player, Privileges.NORMAL)

    await app.state.services.database.execute(
        "INSERT INTO logs "
        "(`from`, `to`, `action`, `msg`, `time`) "
        "VALUES (:from, :to, :action, :msg, NOW())",
        {"from": admin.id, "to": player.id, "action": "restrict", "msg": reason},
    )

    for mode in (0, 1, 2, 3, 4, 5, 6, 8):
        await app.state.services.redis.zrem(
            f"bancho:leaderboard:{mode}",
            player.id,
        )
        await app.state.services.redis.zrem(
            f'bancho:leaderboard:{mode}:{player.geoloc["country"]["acronym"]}',
            player.id,
        )

    log_msg = f"{admin} restricted {player} for: {reason}."

    log(log_msg, Ansi.LRED)

    if webhook_url := app.settings.DISCORD_AUDIT_LOG_WEBHOOK:
        webhook = Webhook(webhook_url, content=log_msg)
        await webhook.post(app.state.services.http)

    if player.online:
        # log the user out if they're offline, this
        # will simply relog them and refresh their app.state
        logout(player)


async def unrestrict(player: Player, admin: Player, reason: str) -> None:
    """Restrict a player with a reason, and log to sql."""
    await add_privs(player, Privileges.NORMAL)

    await app.state.services.database.execute(
        "INSERT INTO logs "
        "(`from`, `to`, `action`, `msg`, `time`) "
        "VALUES (:from, :to, :action, :msg, NOW())",
        {"from": admin.id, "to": player.id, "action": "unrestrict", "msg": reason},
    )

    if not player.online:
        player.stats = await fetch_stats(player.id)

    for mode, stats in player.stats.items():
        await app.state.services.redis.zadd(
            f"bancho:leaderboard:{mode.value}",
            {str(player.id): stats.pp},
        )
        await app.state.services.redis.zadd(
            f"bancho:leaderboard:{mode.value}:{player.geoloc['country']['acronym']}",
            {str(player.id): stats.pp},
        )

    log_msg = f"{admin} unrestricted {player} for: {reason}."

    log(log_msg, Ansi.LRED)

    if webhook_url := app.settings.DISCORD_AUDIT_LOG_WEBHOOK:
        webhook = Webhook(webhook_url, content=log_msg)
        await webhook.post(app.state.services.http)

    if player.online:
        # log the user out if they're offline, this
        # will simply relog them and refresh their app.state
        logout(player)


async def silence(player: Player, admin: Player, duration: int, reason: str) -> None:
    """Silence a player for a duration in seconds, and log to sql."""
    player.silence_end = int(time.time() + duration)

    await app.state.services.database.execute(
        "UPDATE users SET silence_end = :silence_end WHERE id = :user_id",
        {"silence_end": player.silence_end, "user_id": player.id},
    )

    await app.state.services.database.execute(
        "INSERT INTO logs "
        "(`from`, `to`, `action`, `msg`, `time`) "
        "VALUES (:from, :to, :action, :msg, NOW())",
        {"from": admin.id, "to": player.id, "action": "silence", "msg": reason},
    )

    # inform the user's client.
    player.enqueue(app.packets.silence_end(duration))

    # wipe their messages from any channels.
    app.state.sessions.players.enqueue(app.packets.user_silenced(player.id))

    # remove them from multiplayer match (if any).
    if player.match:
        leave_match(player)

    log(f"Silenced {player}.", Ansi.LCYAN)


async def unsilence(player: Player, admin: Player) -> None:
    """Unsilence a player, and log to sql."""
    player.silence_end = int(time.time())

    await app.state.services.database.execute(
        "UPDATE users SET silence_end = :silence_end WHERE id = :user_id",
        {"silence_end": player.silence_end, "user_id": player.id},
    )

    await app.state.services.database.execute(
        "INSERT INTO logs "
        "(`from`, `to`, `action`, `msg`, `time`) "
        "VALUES (:from, :to, :action, NULL, NOW())",
        {"from": admin.id, "to": player.id, "action": "unsilence"},
    )

    # inform the user's client
    player.enqueue(app.packets.silence_end(0))

    log(f"Unsilenced {player}.", Ansi.LCYAN)


def join_match(player: Player, match: Match, passwd: str) -> bool:
    """Attempt to add a player to a multiplayer match."""
    if player.match:
        log(f"{player} tried to join multiple matches?")
        player.enqueue(app.packets.match_join_fail())
        return False

    if player.id in match.tourney_clients:
        # the user is already in the match with a tourney client.
        # users cannot spectate themselves so this is not possible.
        player.enqueue(app.packets.match_join_fail())
        return False

    if player is not match.host:
        # match already exists, we're simply joining.
        # NOTE: staff members have override to pw and can
        # simply use any to join a pw protected match.
        if passwd != match.passwd and player not in app.state.sessions.players.staff:
            log(f"{player} tried to join {match} w/ incorrect pw.", Ansi.LYELLOW)
            player.enqueue(app.packets.match_join_fail())
            return False
        if (slotID := match.get_free()) is None:
            log(f"{player} tried to join a full match.", Ansi.LYELLOW)
            player.enqueue(app.packets.match_join_fail())
            return False

    else:
        # match is being created
        slotID = 0

    if not join_channel(player, match.chat):
        log(f"{player} failed to join {match.chat}.", Ansi.LYELLOW)
        return False

    if (lobby := app.state.sessions.channels["#lobby"]) in player.channels:
        leave_channel(player, lobby)

    slot: Slot = match.slots[0 if slotID == -1 else slotID]

    # if in a teams-vs mode, switch team from neutral to red.
    if match.team_type in (MatchTeamTypes.team_vs, MatchTeamTypes.tag_team_vs):
        slot.team = MatchTeams.red

    slot.status = SlotStatus.not_ready
    slot.player = player
    player.match = match

    player.enqueue(app.packets.match_join_success(match))

    # NOTE: you will need to call app.usecases.multiplayer.send_match_state_to_clients after this

    return True


def leave_match(player: Player) -> None:
    """Attempt to remove a player from their multiplayer match."""
    if not player.match:
        if app.settings.DEBUG:
            log(f"{player} tried leaving a match they're not in?", Ansi.LYELLOW)
        return

    slot = player.match.get_slot(player)
    assert slot is not None

    if slot.status == SlotStatus.locked:
        # player was kicked, keep the slot locked.
        new_status = SlotStatus.locked
    else:
        # player left, open the slot for new players to join.
        new_status = SlotStatus.open

    slot.reset(new_status=new_status)

    leave_channel(player, player.match.chat)

    if all(slot.empty() for slot in player.match.slots):
        # multi is now empty, chat has been removed.
        # remove the multi from the channels list.
        log(f"Match {player.match} finished.")

        # cancel any pending start timers
        if player.match.starting["start"] is not None:
            player.match.starting["start"].cancel()
            for alert in player.match.starting["alerts"]:
                alert.cancel()

            # i guess unnecessary but i'm ocd
            player.match.starting["start"] = None
            player.match.starting["alerts"] = []
            player.match.starting["time"] = 0.0

        app.state.sessions.matches.remove(player.match)

        if lobby := app.state.sessions.channels["#lobby"]:
            app.usecases.channels.send_data_to_clients(
                lobby,
                app.packets.dispose_match(player.match.id),
            )

    else:  # multi is not empty
        if player is player.match.host:
            # player was host, trasnfer to first occupied slot
            for slot in player.match.slots:
                if slot.status & SlotStatus.has_player:
                    player.match.host_id = slot.player.id
                    player.match.host.enqueue(app.packets.match_transfer_host())
                    break

        if player in player.match._refs:
            player.match._refs.remove(player)
            app.usecases.channels.send_bot(
                player.match.chat,
                f"{player.name} removed from match referees.",
            )

        # notify others of our deprature
        app.usecases.multiplayer.send_match_state_to_clients(player.match)

    player.match = None


def join_channel(player: Player, channel: Channel) -> bool:
    """Attempt to add `player` to `c`."""
    if (
        # player already in channel
        player in channel
        # no read privs
        or not app.usecases.channels.can_read(channel, player.priv)
        # not in mp lobby
        or (channel._name == "#lobby" and not player.in_lobby)
    ):
        return False

    app.usecases.channels.join_channel(channel, player)  # add to channel.players
    player.channels.append(channel)  # add to player.channels

    player.enqueue(app.packets.channel_join(channel.name))

    chan_info_packet = app.packets.channel_info(
        channel.name,
        channel.topic,
        len(channel.players),
    )

    if channel.instance:
        # instanced channel, only send the players
        # who are currently inside of the instance
        for p in channel.players:
            p.enqueue(chan_info_packet)
    else:
        # normal channel, send to all players who
        # have access to see the channel's usercount.
        for p in app.state.sessions.players:
            if app.usecases.channels.can_read(channel, p.priv):
                p.enqueue(chan_info_packet)

    if app.settings.DEBUG:
        log(f"{player} joined {channel}.")

    return True


def leave_channel(player: Player, c: Channel, kick: bool = True) -> None:
    """Attempt to remove `player` from `c`."""
    # ensure they're in the chan.
    if player not in c:
        return

    app.usecases.channels.remove_channel(c, player)  # remove from channel.players
    player.channels.remove(c)  # remove from player.channels

    if kick:
        player.enqueue(app.packets.channel_kick(c.name))

    chan_info_packet = app.packets.channel_info(c.name, c.topic, len(c.players))

    if c.instance:
        # instanced channel, only send the players
        # who are currently inside of the instance
        for p in c.players:
            p.enqueue(chan_info_packet)
    else:
        # normal channel, send to all players who
        # have access to see the channel's usercount.
        for p in app.state.sessions.players:
            if app.usecases.channels.can_read(c, p.priv):
                p.enqueue(chan_info_packet)

    if app.settings.DEBUG:
        log(f"{player} left {c}.")


def add_spectator(player: Player, p: Player) -> None:
    """Attempt to add `p` to `player`'s spectators."""
    chan_name = f"#spec_{player.id}"

    if not (spec_chan := app.state.sessions.channels[chan_name]):
        # spectator chan doesn't exist, create it.
        spec_chan = Channel(
            name=chan_name,
            topic=f"{player.name}'s spectator channel.'",
            auto_join=False,
            instance=True,
        )

        join_channel(player, spec_chan)
        app.state.sessions.channels.append(spec_chan)

    # attempt to join their spectator channel.
    if not join_channel(p, spec_chan):
        log(f"{player} failed to join {spec_chan}?", Ansi.LYELLOW)
        return

    if not p.stealth:
        p_joined = app.packets.fellow_spectator_joined(p.id)
        for s in player.spectators:
            s.enqueue(p_joined)
            p.enqueue(app.packets.fellow_spectator_joined(s.id))

        player.enqueue(app.packets.spectator_joined(p.id))
    else:
        # player is admin in stealth, only give
        # other players data to us, not vice-versa.
        for s in player.spectators:
            p.enqueue(app.packets.fellow_spectator_joined(s.id))

    player.spectators.append(p)
    p.spectating = player

    log(f"{p} is now spectating {player}.")


def remove_spectator(player: Player, p: Player) -> None:
    """Attempt to remove `p` from `player`'s spectators."""
    player.spectators.remove(p)
    p.spectating = None

    c = app.state.sessions.channels[f"#spec_{player.id}"]
    leave_channel(p, c)

    if not player.spectators:
        # remove host from channel, deleting it.
        leave_channel(player, c)
    else:
        # send new playercount
        c_info = app.packets.channel_info(c.name, c.topic, len(c.players))
        fellow = app.packets.fellow_spectator_left(p.id)

        player.enqueue(c_info)

        for s in player.spectators:
            s.enqueue(fellow + c_info)

    player.enqueue(app.packets.spectator_left(p.id))
    log(f"{p} is no longer spectating {player}.")


async def add_friend(player: Player, other: Player) -> None:
    """Attempt to add `p` to `player`'s friends."""
    if other.id in player.friends:
        log(
            f"{player} tried to add {other}, who is already their friend!",
            Ansi.LYELLOW,
        )
        return

    player.friends.add(other.id)
    await app.state.services.database.execute(
        "REPLACE INTO relationships (user1, user2, type) VALUES (:user1, :user2, 'friend')",
        {"user1": player.id, "user2": other.id},
    )

    log(f"{player} friended {other}.")


async def remove_friend(player: Player, other: Player) -> None:
    """Attempt to remove `p` from `player`'s friends."""
    if other.id not in player.friends:
        log(
            f"{player} tried to unfriend {other}, who is not their friend!",
            Ansi.LYELLOW,
        )
        return

    player.friends.remove(other.id)
    await app.state.services.database.execute(
        "DELETE FROM relationships WHERE user1 = :user1 AND user2 = :user2",
        {"user1": player.id, "user2": other.id},
    )

    log(f"{player} unfriended {other}.")


async def add_block(player: Player, other: Player) -> None:
    """Attempt to add `p` to `player`'s blocks."""
    if other.id in player.blocks:
        log(
            f"{player} tried to block {other}, who they've already blocked!",
            Ansi.LYELLOW,
        )
        return

    player.blocks.add(other.id)
    await app.state.services.database.execute(
        "REPLACE INTO relationships VALUES (:user1, :user2, 'block')",
        {"user1": player.id, "user2": other.id},
    )

    log(f"{player} blocked {other}.")


async def remove_block(player: Player, other: Player) -> None:
    """Attempt to remove `p` from `player`'s blocks."""
    if other.id not in player.blocks:
        log(
            f"{player} tried to unblock {other}, who they haven't blocked!",
            Ansi.LYELLOW,
        )
        return

    player.blocks.remove(other.id)
    await app.state.services.database.execute(
        "DELETE FROM relationships WHERE user1 = :user1 AND user2 = :user2",
        {"user1": player.id, "user2": other.id},
    )

    log(f"{player} unblocked {other}.")


async def unlock_achievement(player: Player, achievement: "Achievement") -> None:
    """Unlock `ach` for `player`, storing in both cache & sql."""
    await app.state.services.database.execute(
        "INSERT INTO user_achievements (userid, achid) VALUES (:user_id, :ach_id)",
        {"user_id": player.id, "ach_id": achievement.id},
    )

    player.achievements.add(achievement)


async def fetch_relationships(player_id: int) -> tuple[set[int], set[int]]:
    """Retrieve `player`'s relationships from sql."""
    player_friends = set()
    player_blocks = set()

    for row in await app.state.services.database.fetch_all(
        "SELECT user2, type FROM relationships WHERE user1 = :user1",
        {"user1": player_id},
    ):
        if row["type"] == "friend":
            player_friends.add(row["user2"])
        else:
            player_blocks.add(row["user2"])

    # always have bot added to friends.
    player_friends.add(1)

    return player_friends, player_blocks


async def fetch_achievements(player_id: int) -> set[Achievement]:
    """Retrieve `player`'s achievements from sql."""
    player_achievements = set()

    for row in await app.state.services.database.fetch_all(
        "SELECT ua.achid id FROM user_achievements ua "
        "INNER JOIN achievements a ON a.id = ua.achid "
        "WHERE ua.userid = :user_id",
        {"user_id": player_id},
    ):
        for ach in app.state.sessions.achievements:
            if row["id"] == ach.id:
                player_achievements.add(ach)

    return player_achievements


async def get_global_rank(player_id: int, mode: GameMode) -> int:
    rank = await app.state.services.redis.zrevrank(
        f"bancho:leaderboard:{mode.value}",
        str(player_id),
    )
    return rank + 1 if rank is not None else 0


async def get_country_rank(player_id: int, mode: GameMode, country: str) -> int:
    rank = await app.state.services.redis.zrevrank(
        f"bancho:leaderboard:{mode.value}:{country}",
        str(player_id),
    )

    return rank + 1 if rank is not None else 0


async def update_rank(player: Player, mode: GameMode) -> int:
    country = player.geoloc["country"]["acronym"]
    stats = player.stats[mode]

    # global rank
    await app.state.services.redis.zadd(
        f"bancho:leaderboard:{mode.value}",
        {str(player.id): stats.pp},
    )

    # country rank
    await app.state.services.redis.zadd(
        f"bancho:leaderboard:{mode.value}:{country}",
        {str(player.id): stats.pp},
    )

    if player.restricted:
        global_rank = 0
    else:
        global_rank = await get_global_rank(player.id, mode)

    return global_rank


async def fetch_stats(player_id: int) -> Mapping[GameMode, ModeData]:
    """Retrieve `player`'s stats (all modes) from sql."""
    player_stats: Mapping[GameMode, ModeData] = {}

    for row in await app.state.services.database.fetch_all(
        "SELECT mode, tscore, rscore, pp, acc, "
        "plays, playtime, max_combo, total_hits, "
        "xh_count, x_count, sh_count, s_count, a_count "
        "FROM stats "
        "WHERE id = :user_id",
        {"user_id": player_id},
    ):
        row = dict(row)  # make mutable copy
        mode = row.pop("mode")

        # calculate player's rank.
        row["rank"] = await get_global_rank(player_id, GameMode(mode))

        row["grades"] = {
            Grade.XH: row.pop("xh_count"),
            Grade.X: row.pop("x_count"),
            Grade.SH: row.pop("sh_count"),
            Grade.S: row.pop("s_count"),
            Grade.A: row.pop("a_count"),
        }

        player_stats[GameMode(mode)] = ModeData(**row)

    return player_stats


def send_menu_clear(player: Player) -> None:
    """Clear the user's osu! chat with the bot
    to make room for a new menu to be sent."""
    # NOTE: the only issue with this is that it will
    # wipe any messages the client can see from the bot
    # (including any other channels). perhaps menus can
    # be sent from a separate presence to prevent this?
    player.enqueue(app.packets.user_silenced(app.state.sessions.bot.id))


def send_current_menu(player: Player) -> None:
    """Forward a standardized form of the user's
    current menu to them via the osu! chat."""
    msg = [player.current_menu.name]

    for key, (cmd, data) in player.current_menu.options.items():
        val = data.name if data else "Back"
        msg.append(f"[osump://{key}/ {val}]")

    chat_height = 10
    lines_used = len(msg)
    if lines_used < chat_height:
        msg += [chr(8192)] * (chat_height - lines_used)

    send_menu_clear(player)
    send_bot(player, "\n".join(msg))


def update_latest_activity_soon(player: Player) -> None:
    """Update the player's latest activity in the database."""
    task = app.state.services.database.execute(
        "UPDATE users SET latest_activity = UNIX_TIMESTAMP() WHERE id = :user_id",
        {"user_id": player.id},
    )
    app.state.loop.create_task(task)


def send(
    player: Player,
    msg: str,
    sender: Player,
    chan: Optional[Channel] = None,
) -> None:
    """Enqueue `sender`'s `msg` to `player`. Sent in `chan`, or dm."""
    player.enqueue(
        app.packets.send_message(
            sender=sender.name,
            msg=msg,
            recipient=(chan or player).name,
            sender_id=sender.id,
        ),
    )


def send_bot(player: Player, msg: str) -> None:
    """Enqueue `msg` to `player` from bot."""
    bot = app.state.sessions.bot

    player.enqueue(
        app.packets.send_message(
            sender=bot.name,
            msg=msg,
            recipient=player.name,
            sender_id=bot.id,
        ),
    )


async def get_favourite_beatmap_sets(player: Player) -> list[int]:
    """Return a list of the user's favourite map set ids."""
    rows = await app.state.services.database.fetch_all(
        "SELECT setid FROM favourites WHERE userid = :user_id",
        {"user_id": player.id},
    )

    return [row["setid"] for row in rows]


async def add_favourite(player: Player, map_set_id: int) -> bytes:
    async with app.state.services.database.connection() as db_conn:
        # check if they already have this favourited.
        if await db_conn.fetch_one(
            "SELECT 1 FROM favourites WHERE userid = :user_id AND setid = :set_id",
            {"user_id": player.id, "set_id": map_set_id},
        ):
            return b"You've already favourited this beatmap!"

        # add favourite
        await db_conn.execute(
            "INSERT INTO favourites VALUES (:user_id, :set_id)",
            {"user_id": player.id, "set_id": map_set_id},
        )

    return b""
