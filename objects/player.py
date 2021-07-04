# -*- coding: utf-8 -*-

import random
import time
import uuid
from dataclasses import dataclass
from datetime import date
from enum import IntEnum
from enum import unique
from functools import cached_property
from functools import partial
from typing import Coroutine
from typing import Optional
from typing import TYPE_CHECKING
from typing import Union

import aiomysql
from cmyui.logging import Ansi
from cmyui.logging import log
from cmyui.discord import Webhook

import packets
from constants.gamemodes import GameMode
from constants.mods import Mods
from constants.privileges import ClientPrivileges
from constants.privileges import Privileges
from objects import glob
from objects.channel import Channel
from objects.match import Match
from objects.match import MatchTeams
from objects.match import MatchTeamTypes
from objects.match import Slot
from objects.match import SlotStatus
from objects.menu import Menu
from objects.menu import MenuCommands
from objects.menu import MenuFunction
from objects.menu import menu_keygen
from utils.misc import escape_enum
from utils.misc import pymysql_encode

if TYPE_CHECKING:
    from objects.score import Score
    from objects.achievement import Achievement
    from objects.clan import Clan
    from objects.clan import ClanPrivileges

__all__ = (
    'ModeData',
    'Status',
    'Player'
)

BASE_DOMAIN = glob.config.domain

@unique
@pymysql_encode(escape_enum)
class PresenceFilter(IntEnum):
    """osu! client side filter for which users the player can see."""
    Nil     = 0
    All     = 1
    Friends = 2

@unique
@pymysql_encode(escape_enum)
class Action(IntEnum):
    """The client's current state."""
    Idle         = 0
    Afk          = 1
    Playing      = 2
    Editing      = 3
    Modding      = 4
    Multiplayer  = 5
    Watching     = 6
    Unknown      = 7
    Testing      = 8
    Submitting   = 9
    Paused       = 10
    Lobby        = 11
    Multiplaying = 12
    OsuDirect    = 13

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
    rank: int # global

@dataclass
class Status:
    """The current status of a player."""
    action: Action = Action.Idle
    info_text: str = ''
    map_md5: str = ''
    mods: Mods = Mods.NOMOD
    mode: GameMode = GameMode.vn_std
    map_id: int = 0

# temporary menu-related stuff
async def bot_hello(p: 'Player') -> None:
    p.send_bot(f'hello {p.name}!')

async def notif_hello(p: 'Player') -> None:
    p.enqueue(packets.notification(f'hello {p.name}!'))

MENU2 = Menu('Second Menu', {
    menu_keygen(): (MenuCommands.Back, None),
    menu_keygen(): (MenuCommands.Execute, MenuFunction('notif_hello', notif_hello)),
})

MAIN_MENU = Menu('Main Menu', {
    menu_keygen(): (MenuCommands.Execute, MenuFunction('bot_hello', bot_hello)),
    menu_keygen(): (MenuCommands.Execute, MenuFunction('notif_hello', notif_hello)),
    menu_keygen(): (MenuCommands.Advance, MENU2)
})

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

    bot_client: `bool`
        Whether this is a bot account.

    tourney_client: `bool`
        Whether this is a management/spectator tourney client.

    _queue: `bytearray`
        Bytes enqueued to the player which will be transmitted
        at the tail end of their next connection to the server.
        XXX: cls.enqueue() will add data to this queue, and
             cls.dequeue() will return the data, and remove it.
    """
    __slots__ = (
        'token', 'id', 'name', 'safe_name', 'pw_bcrypt',
        'priv', 'stats', 'status', 'friends', 'blocks', 'channels',
        'spectators', 'spectating', 'match', 'stealth',
        'clan', 'clan_priv', 'achievements',
        'recent_scores', 'last_np', 'country', 'location',
        'utc_offset', 'pm_private',
        'away_msg', 'silence_end', 'in_lobby', 'osu_ver',
        'pres_filter', 'login_time', 'last_recv_time',

        'current_menu', 'previous_menus',

        'bot_client', 'tourney_client',
        'api_key', '_queue',
        '__dict__'
    )

    def __init__(self, id: int, name: str,
                 priv: Union[Privileges, int], **extras) -> None:
        self.id = id
        self.name = name
        self.safe_name = self.make_safe(self.name)

        self.pw_bcrypt = extras.get('pw_bcrypt', None)

        # generate a token if not given
        token = extras.get('token', None)
        if token is not None:
            self.token = token
        else:
            self.token = self.generate_token()

        # ensure priv is of type Privileges
        self.priv = (priv if isinstance(priv, Privileges) else
                     Privileges(priv))

        self.stats: dict[GameMode, ModeData] = {}
        self.status = Status()

        # userids, not player objects
        self.friends: set[int] = set()
        self.blocks: set[int] = set()

        self.channels: list[Channel] = []
        self.spectators: list[Player] = []
        self.spectating: Optional[Player] = None
        self.match: Optional[Match] = None
        self.stealth = False

        self.clan: Optional['Clan'] = extras.get('clan', None)
        self.clan_priv: Optional['ClanPrivileges'] = extras.get('clan_priv', None)

        self.achievements: set['Achievement'] = set()

        self.geoloc = extras.get('geoloc', {
            'latitude': 0.0,
            'longitude': 0.0,
            'country': {
                'acronym': 'xx',
                'numeric': 0
            }
        })

        self.utc_offset = extras.get('utc_offset', 0)
        self.pm_private = extras.get('pm_private', False)
        self.away_msg: Optional[str] = None
        self.silence_end = extras.get('silence_end', 0)
        self.in_lobby = False
        self.osu_ver: Optional[date] = extras.get('osu_ver', None)
        self.pres_filter = PresenceFilter.Nil

        login_time = extras.get('login_time', 0.0)
        self.login_time = login_time
        self.last_recv_time = login_time

        # XXX: below is mostly gulag-specific & internal stuff

        # store most recent score for each gamemode.
        self.recent_scores: dict[GameMode, Optional['Score']] = {
            mode: None for mode in GameMode
        }

        # store the last beatmap /np'ed by the user.
        self.last_np = {
            'bmap': None,
            'mode_vn': None,
            'timeout': 0
        }

        # TODO: document
        self.current_menu = MAIN_MENU
        self.previous_menus = []

        # subject to possible change in the future,
        # although if anything, bot accounts will
        # probably just use the /api/ routes?
        self.bot_client = extras.get('bot_client', False)
        if self.bot_client:
            self.enqueue = lambda data: None

        self.tourney_client = extras.get('tourney_client', False)

        self.api_key = extras.get('api_key', None)

        # packet queue
        self._queue = bytearray()

    def __repr__(self) -> str:
        return f'<{self.name} ({self.id})>'

    @cached_property
    def online(self) -> bool:
        return self.token != ''

    @cached_property
    def url(self) -> str:
        """The url to the player's profile."""
        # NOTE: this is currently never wiped because
        # domain & id cannot be changed in-game; if this
        # ever changes, it will need to be wiped.
        return f'https://{BASE_DOMAIN}/u/{self.id}'

    @cached_property
    def embed(self) -> str:
        """An osu! chat embed to the player's profile."""
        # NOTE: this is currently never wiped because
        # url & name cannot be changed in-game; if this
        # ever changes, it will need to be wiped.
        return f'[{self.url} {self.name}]'

    @cached_property
    def avatar_url(self) -> str:
        """The url to the player's avatar."""
        # NOTE: this is currently never wiped because
        # domain & id cannot be changed in-game; if this
        # ever changes, it will need to be wiped.
        return f'https://a.{BASE_DOMAIN}/{self.id}'

    @cached_property
    def full_name(self) -> str:
        """The user's "full" name; including their clan tag."""
        # NOTE: this is currently only wiped when the
        # user leaves their clan; if name/clantag ever
        # become changeable, it will need to be wiped.
        if self.clan:
            return f'[{self.clan.tag}] {self.name}'
        else:
            return self.name

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
        if self.priv & Privileges.Normal:
            ret |= ClientPrivileges.Player
        if self.priv & Privileges.Donator:
            ret |= ClientPrivileges.Supporter
        if self.priv & Privileges.Mod:
            ret |= ClientPrivileges.Moderator
        if self.priv & Privileges.Admin:
            ret |= ClientPrivileges.Developer
        if self.priv & Privileges.Dangerous:
            ret |= ClientPrivileges.Owner
        return ret

    @cached_property
    def restricted(self) -> bool:
        """Return whether the player is restricted."""
        return not self.priv & Privileges.Normal

    @property
    def gm_stats(self) -> ModeData:
        """The player's stats in their currently selected mode."""
        return self.stats[self.status.mode]

    @cached_property
    def recent_score(self) -> 'Score':
        """The player's most recently submitted score."""
        score = None
        for s in self.recent_scores.values():
            if not s:
                continue

            if not score:
                score = s
                continue

            if s.play_time > score.play_time:
                score = s

        return score

    @staticmethod
    def generate_token() -> str:
        """Generate a random uuid as a token."""
        return str(uuid.uuid4())

    @staticmethod
    def make_safe(name: str) -> str:
        """Return a name safe for usage in sql."""
        return name.lower().replace(' ', '_')

    def logout(self) -> None:
        """Log `self` out of the server."""
        # invalidate the user's token.
        self.token = ''

        if 'online' in self.__dict__:
            del self.online # wipe cached_property

        # leave multiplayer.
        if self.match:
            self.leave_match()

        # stop spectating.
        if host := self.spectating:
            host.remove_spectator(self)

        # leave channels
        while self.channels:
            self.leave_channel(self.channels[0], kick=False)

        # remove from playerlist and
        # enqueue logout to all users.
        glob.players.remove(self)

        if not self.restricted:
            if glob.datadog:
                glob.datadog.decrement('gulag.online_players')

            glob.players.enqueue(packets.logout(self.id))

        log(f'{self} logged out.', Ansi.LYELLOW)

    async def update_privs(self, new: Privileges) -> None:
        """Update `self`'s privileges to `new`."""
        self.priv = new

        await glob.db.execute(
            'UPDATE users '
            'SET priv = %s '
            'WHERE id = %s',
            [self.priv, self.id]
        )

        if 'bancho_priv' in self.__dict__:
            del self.bancho_priv # wipe cached_property

    async def add_privs(self, bits: Privileges) -> None:
        """Update `self`'s privileges, adding `bits`."""
        self.priv |= bits

        await glob.db.execute(
            'UPDATE users '
            'SET priv = %s '
            'WHERE id = %s',
            [self.priv, self.id]
        )

        if 'bancho_priv' in self.__dict__:
            del self.bancho_priv # wipe cached_property

    async def remove_privs(self, bits: Privileges) -> None:
        """Update `self`'s privileges, removing `bits`."""
        self.priv &= ~bits

        await glob.db.execute(
            'UPDATE users '
            'SET priv = %s '
            'WHERE id = %s',
            [self.priv, self.id]
        )

        if 'bancho_priv' in self.__dict__:
            del self.bancho_priv # wipe cached_property

    async def restrict(self, admin: 'Player', reason: str) -> None:
        """Restrict `self` for `reason`, and log to sql."""
        await self.remove_privs(Privileges.Normal)

        log_msg = f'{admin} restricted for "{reason}".'
        await glob.db.execute(
            'INSERT INTO logs '
            '(`from`, `to`, `msg`, `time`) '
            'VALUES (%s, %s, %s, NOW())',
            [admin.id, self.id, log_msg]
        )

        if 'restricted' in self.__dict__:
            del self.restricted # wipe cached_property

        log_msg = f'{admin} restricted {self} for: {reason}.'

        log(log_msg, Ansi.LRED)

        if glob.has_internet:
            if webhook_url := glob.config.webhooks['audit-log']:
                webhook = Webhook(webhook_url, content=log_msg)
                await webhook.post(glob.http)

        if self.online:
            # log the user out if they're offline, this
            # will simply relog them and refresh their state.
            self.logout()

    async def unrestrict(self, admin: 'Player', reason: str) -> None:
        """Restrict `self` for `reason`, and log to sql."""
        await self.add_privs(Privileges.Normal)

        log_msg = f'{admin} unrestricted for "{reason}".'
        await glob.db.execute(
            'INSERT INTO logs '
            '(`from`, `to`, `msg`, `time`) '
            'VALUES (%s, %s, %s, NOW())',
            [admin.id, self.id, log_msg]
        )

        if 'restricted' in self.__dict__:
            del self.restricted # wipe cached_property

        log_msg = f'{admin} unrestricted {self} for: {reason}.'

        log(log_msg, Ansi.LRED)

        if glob.has_internet:
            if webhook_url := glob.config.webhooks['audit-log']:
                webhook = Webhook(webhook_url, content=log_msg)
                await webhook.post(glob.http)

        if self.online:
            # log the user out if they're offline, this
            # will simply relog them and refresh their state.
            self.logout()

    async def silence(self, admin: 'Player', duration: int,
                      reason: str) -> None:
        """Silence `self` for `duration` seconds, and log to sql."""
        self.silence_end = int(time.time() + duration)

        await glob.db.execute(
            'UPDATE users SET silence_end = %s WHERE id = %s',
            [self.silence_end, self.id]
        )

        log_msg = f'{admin} silenced ({duration}s) for "{reason}".'
        await glob.db.execute(
            'INSERT INTO logs '
            '(`from`, `to`, `msg`, `time`) '
            'VALUES (%s, %s, %s, NOW())',
            [admin.id, self.id, log_msg]
        )

        # inform the user's client.
        self.enqueue(packets.silenceEnd(duration))

        # wipe their messages from any channels.
        glob.players.enqueue(packets.userSilenced(self.id))

        # remove them from multiplayer match (if any).
        if self.match:
            self.leave_match()

        log(f'Silenced {self}.', Ansi.LCYAN)

    async def unsilence(self, admin: 'Player') -> None:
        """Unsilence `self`, and log to sql."""
        self.silence_end = int(time.time())

        await glob.db.execute(
            'UPDATE users SET silence_end = %s WHERE id = %s',
            [self.silence_end, self.id]
        )

        log_msg = f'{admin} unsilenced.'
        await glob.db.execute(
            'INSERT INTO logs '
            '(`from`, `to`, `msg`, `time`) '
            'VALUES (%s, %s, %s, NOW())',
            [admin.id, self.id, log_msg]
        )

        # inform the user's client
        self.enqueue(packets.silenceEnd(0))

        log(f'Unsilenced {self}.', Ansi.LCYAN)

    def join_match(self, m: Match, passwd: str) -> bool:
        """Attempt to add `self` to `m`."""
        if self.match:
            log(f'{self} tried to join multiple matches?')
            self.enqueue(packets.matchJoinFail())
            return False

        if self.id in m.tourney_clients:
            # the user is already in the match with a tourney client.
            # users cannot spectate themselves so this is not possible.
            self.enqueue(packets.matchJoinFail())
            return False

        if self is not m.host:
            # match already exists, we're simply joining.
            # NOTE: staff members have override to pw and can
            # simply use any to join a pw protected match.
            if (
                passwd != m.passwd and
                self not in glob.players.staff
            ):
                log(f'{self} tried to join {m} w/ incorrect pw.', Ansi.LYELLOW)
                self.enqueue(packets.matchJoinFail())
                return False
            if (slotID := m.get_free()) is None:
                log(f'{self} tried to join a full match.', Ansi.LYELLOW)
                self.enqueue(packets.matchJoinFail())
                return False

        else:
            # match is being created
            slotID = 0

        if not self.join_channel(m.chat):
            log(f'{self} failed to join {m.chat}.', Ansi.LYELLOW)
            return False

        if (lobby := glob.channels['#lobby']) in self.channels:
            self.leave_channel(lobby)

        slot: Slot = m.slots[0 if slotID == -1 else slotID]

        # if in a teams-vs mode, switch team from neutral to red.
        if m.team_type in (MatchTeamTypes.team_vs,
                           MatchTeamTypes.tag_team_vs):
            slot.team = MatchTeams.red

        slot.status = SlotStatus.not_ready
        slot.player = self
        self.match = m

        self.enqueue(packets.matchJoinSuccess(m))
        m.enqueue_state()

        return True

    def leave_match(self) -> None:
        """Attempt to remove `self` from their match."""
        if not self.match:
            if glob.app.debug:
                log(f"{self} tried leaving a match they're not in?", Ansi.LYELLOW)
            return

        slot = self.match.get_slot(self)

        if slot.status == SlotStatus.locked:
            # player was kicked, keep the slot locked.
            new_status = SlotStatus.locked
        else:
            # player left, open the slot for new players to join.
            new_status = SlotStatus.open

        slot.reset(new_status=new_status)

        self.leave_channel(self.match.chat)

        if all(map(Slot.empty, self.match.slots)):
            # multi is now empty, chat has been removed.
            # remove the multi from the channels list.
            log(f'Match {self.match} finished.')

            # cancel any pending start timers
            if self.match.starting['start'] is not None:
                self.match.starting['start'].cancel()
                for alert in self.match.starting['alerts']:
                    alert.cancel()

                # i guess unnecessary but i'm ocd
                self.match.starting['start'] = None
                self.match.starting['alerts'] = None
                self.match.starting['time'] = None

            glob.matches.remove(self.match)

            if lobby := glob.channels['#lobby']:
                lobby.enqueue(packets.disposeMatch(self.match.id))

        else:
            # we may have been host, if so, find another.
            if self is self.match.host:
                for s in self.match.slots:
                    if s.status & SlotStatus.has_player:
                        self.match.host = s.player
                        self.match.host.enqueue(packets.matchTransferHost())
                        break

            if self in self.match._refs:
                self.match._refs.remove(self)
                self.match.chat.send_bot(f'{self.name} removed from match referees.')

            # notify others of our deprature
            self.match.enqueue_state()

        self.match = None

    async def join_clan(self, c: 'Clan') -> bool:
        """Attempt to add `self` to `c`."""
        if self.id in c.members:
            return False

        if not 'invited': # TODO
            return False

        await c.add_member(self)
        return True

    async def leave_clan(self) -> None:
        """Attempt to remove `self` from `c`."""
        if not self.clan:
            return

        await self.clan.remove_member(self)

    def join_channel(self, c: Channel) -> bool:
        """Attempt to add `self` to `c`."""
        if (
            self in c or # player already in channel
            not c.can_read(self.priv) or # no read privs
            c._name == '#lobby' and not self.in_lobby # not in mp lobby
        ):
            return False

        c.append(self) # add to c.players
        self.channels.append(c) # add to p.channels

        self.enqueue(packets.channelJoin(c.name))

        chan_info_packet = packets.channelInfo(
            c.name, c.topic, len(c.players)
        )

        if c.instance:
            # instanced channel, only send the players
            # who are currently inside of the instance
            for p in c.players:
                p.enqueue(chan_info_packet)
        else:
            # normal channel, send to all players who
            # have access to see the channel's usercount.
            for p in glob.players:
                if c.can_read(p.priv):
                    p.enqueue(chan_info_packet)

        if glob.app.debug:
            log(f'{self} joined {c}.')

        return True

    def leave_channel(self, c: Channel, kick: bool = True) -> None:
        """Attempt to remove `self` from `c`."""
        # ensure they're in the chan.
        if self not in c:
            return

        c.remove(self) # remove from c.players
        self.channels.remove(c) # remove from p.channels

        if kick:
            self.enqueue(packets.channelKick(c.name))

        chan_info_packet = packets.channelInfo(
            c.name, c.topic, len(c.players)
        )

        if c.instance:
            # instanced channel, only send the players
            # who are currently inside of the instance
            for p in c.players:
                p.enqueue(chan_info_packet)
        else:
            # normal channel, send to all players who
            # have access to see the channel's usercount.
            for p in glob.players:
                if c.can_read(p.priv):
                    p.enqueue(chan_info_packet)

        if glob.app.debug:
            log(f'{self} left {c}.')

    def add_spectator(self, p: 'Player') -> None:
        """Attempt to add `p` to `self`'s spectators."""
        chan_name = f'#spec_{self.id}'

        if not (spec_chan := glob.channels[chan_name]):
            # spectator chan doesn't exist, create it.
            spec_chan = Channel(
                name = chan_name,
                topic = f"{self.name}'s spectator channel.'",
                auto_join = False,
                instance = True
            )

            self.join_channel(spec_chan)
            glob.channels.append(spec_chan)

        # attempt to join their spectator channel.
        if not p.join_channel(spec_chan):
            log(f'{self} failed to join {spec_chan}?', Ansi.LYELLOW)
            return

        if not p.stealth:
            p_joined = packets.fellowSpectatorJoined(p.id)
            for s in self.spectators:
                s.enqueue(p_joined)
                p.enqueue(packets.fellowSpectatorJoined(s.id))

            self.enqueue(packets.spectatorJoined(p.id))
        else:
            # player is admin in stealth, only give
            # other players data to us, not vice-versa.
            for s in self.spectators:
                p.enqueue(packets.fellowSpectatorJoined(s.id))

        self.spectators.append(p)
        p.spectating = self

        log(f'{p} is now spectating {self}.')

    def remove_spectator(self, p: 'Player') -> None:
        """Attempt to remove `p` from `self`'s spectators."""
        self.spectators.remove(p)
        p.spectating = None

        c = glob.channels[f'#spec_{self.id}']
        p.leave_channel(c)

        if not self.spectators:
            # remove host from channel, deleting it.
            self.leave_channel(c)
        else:
            # send new playercount
            c_info = packets.channelInfo(c.name, c.topic, len(c.players))
            fellow = packets.fellowSpectatorLeft(p.id)

            self.enqueue(c_info)

            for s in self.spectators:
                s.enqueue(fellow + c_info)

        self.enqueue(packets.spectatorLeft(p.id))
        log(f'{p} is no longer spectating {self}.')

    async def add_friend(self, p: 'Player') -> None:
        """Attempt to add `p` to `self`'s friends."""
        if p.id in self.friends:
            log(f'{self} tried to add {p}, who is already their friend!', Ansi.LYELLOW)
            return

        self.friends.add(p.id)
        await glob.db.execute(
            "REPLACE INTO relationships "
            "VALUES (%s, %s, 'friend')",
            [self.id, p.id]
        )

        log(f'{self} friended {p}.')

    async def remove_friend(self, p: 'Player') -> None:
        """Attempt to remove `p` from `self`'s friends."""
        if p.id not in self.friends:
            log(f'{self} tried to unfriend {p}, who is not their friend!', Ansi.LYELLOW)
            return

        self.friends.remove(p.id)
        await glob.db.execute(
            'DELETE FROM relationships '
            'WHERE user1 = %s AND user2 = %s',
            [self.id, p.id]
        )

        log(f'{self} unfriended {p}.')

    async def add_block(self, p: 'Player') -> None:
        """Attempt to add `p` to `self`'s blocks."""
        if p.id in self.blocks:
            log(f"{self} tried to block {p}, who they've already blocked!", Ansi.LYELLOW)
            return

        self.blocks.add(p.id)
        await glob.db.execute(
            "REPLACE INTO relationships "
            "VALUES (%s, %s, 'block')",
            [self.id, p.id]
        )

        log(f'{self} blocked {p}.')

    async def remove_block(self, p: 'Player') -> None:
        """Attempt to remove `p` from `self`'s blocks."""
        if p.id not in self.blocks:
            log(f"{self} tried to unblock {p}, who they haven't blocked!", Ansi.LYELLOW)
            return

        self.blocks.remove(p.id)
        await glob.db.execute(
            'DELETE FROM relationships '
            'WHERE user1 = %s AND user2 = %s',
            [self.id, p.id]
        )

        log(f'{self} unblocked {p}.')

    async def unlock_achievement(self, a: 'Achievement') -> None:
        """Unlock `ach` for `self`, storing in both cache & sql."""
        await glob.db.execute(
            'INSERT INTO user_achievements '
            '(userid, achid) '
            'VALUES (%s, %s)',
            [self.id, a.id]
        )

        self.achievements.add(a)

    async def relationships_from_sql(self, db_cursor: aiomysql.DictCursor) -> None:
        """Retrieve `self`'s relationships from sql."""
        await db_cursor.execute(
            'SELECT user2, type '
            'FROM relationships '
            'WHERE user1 = %s',
            [self.id]
        )

        async for row in db_cursor:
            if row['type'] == 'friend':
                self.friends.add(row['user2'])
            else:
                self.blocks.add(row['user2'])

        # always have bot added to friends.
        self.friends.add(1)

    async def achievements_from_sql(self, db_cursor: aiomysql.DictCursor) -> None:
        """Retrieve `self`'s achievements from sql."""
        await db_cursor.execute(
            'SELECT ua.achid id FROM user_achievements ua '
            'INNER JOIN achievements a ON a.id = ua.achid '
            'WHERE ua.userid = %s',
            [self.id]
        )

        async for row in db_cursor:
            for ach in glob.achievements:
                if row['id'] == ach.id:
                    self.achievements.add(ach)

    async def stats_from_sql_full(self, db_cursor: aiomysql.DictCursor) -> None:
        """Retrieve `self`'s stats (all modes) from sql."""
        await db_cursor.execute(
            'SELECT * '
            'FROM stats '
            'WHERE id = %s',
            [self.id]
        )

        res = await db_cursor.fetchone()

        # get global rank for each mode
        # XXX: this will be improved in future
        for mode in GameMode:
            mode_suffix = format(mode, 'sql')

            # calculate rank.
            await db_cursor.execute(
                'SELECT COUNT(*) AS higher_pp_players '
                'FROM stats s '
                'INNER JOIN users u USING(id) '
                f'WHERE s.pp_{mode_suffix} > %s '
                'AND u.priv & 1 and u.id != %s',
                [res[f'pp_{mode_suffix}'], self.id]
            )

            mode_rank = (await db_cursor.fetchone())['higher_pp_players'] + 1

            # update stats
            self.stats[mode] = ModeData(
                tscore=res[f'tscore_{mode_suffix}'],
                rscore=res[f'rscore_{mode_suffix}'],
                pp=res[f'pp_{mode_suffix}'],
                acc=res[f'acc_{mode_suffix}'],
                plays=res[f'plays_{mode_suffix}'],
                playtime=res[f'playtime_{mode_suffix}'],
                max_combo=res[f'max_combo_{mode_suffix}'],
                rank=mode_rank
            )

    def send_menu_clear(self) -> None:
        """Clear the user's osu! chat with the bot
           to make room for a new menu to be sent."""
        # NOTE: the only issue with this is that it will
        # wipe any messages the client can see from the bot
        # (including any other channels). perhaps menus can
        # be sent from a separate presence to prevent this?
        self.enqueue(packets.userSilenced(glob.bot.id))

    def send_current_menu(self) -> None:
        """Forward a standardized form of the user's
           current menu to them via the osu! chat."""
        msg = [self.current_menu.name]

        for key, (cmd, data) in self.current_menu.options.items():
            val = data.name if data else 'Back'
            msg.append(f'[osump://{key}/ {val}]')

        chat_height = 10
        lines_used = len(msg)
        if lines_used < chat_height:
            msg += [chr(8192)] * (chat_height - lines_used)

        self.send_menu_clear()
        self.send_bot('\n'.join(msg))

    def update_latest_activity(self) -> None:
        """Update the player's latest activity in the database."""
        task = glob.db.execute(
            'UPDATE users '
            'SET latest_activity = UNIX_TIMESTAMP() '
            'WHERE id = %s',
            [self.id]
        )
        glob.loop.create_task(task)

    def enqueue(self, b: bytes) -> None:
        """Add data to be sent to the client."""
        self._queue += b

    def dequeue(self) -> Optional[bytes]:
        """Get data from the queue to send to the client."""
        if self._queue:
            data = bytes(self._queue)
            self._queue.clear()
            return data

    def send(self, msg: str, sender: 'Player',
             chan: Optional[Channel] = None) -> None:
        """Enqueue `sender`'s `msg` to `self`. Sent in `chan`, or dm."""
        self.enqueue(
            packets.sendMessage(
                sender = sender.name,
                msg = msg,
                recipient = (chan or self).name,
                sender_id = sender.id
            )
        )

    def send_bot(self, msg: str) -> None:
        """Enqueue `msg` to `self` from bot."""
        bot = glob.bot

        self.enqueue(
            packets.sendMessage(
                sender = bot.name,
                msg = msg,
                recipient = self.name,
                sender_id = bot.id
            )
        )
