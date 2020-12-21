# -*- coding: utf-8 -*-

from datetime import datetime
from functools import partial
from typing import TYPE_CHECKING, Any, Optional, Coroutine
from dataclasses import dataclass
from enum import IntEnum, unique
from cmyui import log, Ansi
import queue
import time
import uuid
import random

from constants.privileges import Privileges, ClientPrivileges
from constants.countries import country_codes
from constants.gamemodes import GameMode
from constants.mods import Mods

from objects.channel import Channel
from objects.match import Match, SlotStatus, MatchTeamTypes, MatchTeams
from objects.beatmap import Beatmap
from objects import glob

import packets

if TYPE_CHECKING:
    from objects.score import Score

__all__ = (
    'ModeData',
    'Status',
    'Player'
)

@unique
class PresenceFilter(IntEnum):
    """osu! client side filter for which users the player can see."""
    Nil     = 0
    All     = 1
    Friends = 2

@unique
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

    # XXX: below is mostly custom gulag,
           or internal player class stuff.

    menu_options: `dict[int, dict[str, Any]]`
        The current osu! chat menu options available to the player.
        XXX: These may eventually have a timeout.

    _queue: `queue.SimpleQueue`
        A `SimpleQueue` obj representing our packet queue.
        XXX: cls.enqueue() will add data to this queue, and
             cls.dequeue() will return the data, and remove it.
    """
    __slots__ = (
        'token', 'id', 'name', 'safe_name', 'priv',
        'stats', 'status', 'friends', 'channels',
        'spectators', 'spectating', 'match',
        'recent_scores', 'last_np', 'country', 'location',
        'utc_offset', 'pm_private',
        'away_msg', 'silence_end', 'in_lobby',
        'login_time', 'last_recv_time', 'osu_ver',
        'pres_filter', 'menu_options', '_queue'
    )

    def __init__(self, id: int, name: str, priv: int,
                 utc_offset: int = 0, pm_private: bool = False,
                 silence_end: int = 0, osu_ver: Optional[datetime] = None) -> None:
        self.id = id
        self.name = name
        self.priv = Privileges(priv)

        self.token = self.generate_token()
        self.safe_name = self.make_safe(self.name)

        self.stats = {mode: None for mode in GameMode}
        self.status = Status()

        self.friends: set[int] = set() # userids, not player objects
        self.channels: list[Channel] = []
        self.spectators: list[Player] = []
        self.spectating: Optional[Player] = None
        self.match: Optional[Match] = None

        self.country = (0, 'XX') # (code, letters)
        self.location = (0.0, 0.0) # (lat, long)

        self.utc_offset = utc_offset
        self.pm_private = pm_private

        self.away_msg: Optional[str] = None
        self.silence_end = silence_end
        self.in_lobby = False

        _ctime = int(time.time())
        self.login_time = _ctime
        self.last_recv_time = _ctime

        self.osu_ver = osu_ver
        self.pres_filter = PresenceFilter.Nil

        # XXX: below is mostly gulag-specific & internal stuff

        # store most recent score for each gamemode.
        self.recent_scores = {mode: None for mode in GameMode}

        # store the last beatmap /np'ed by the user.
        self.last_np: Optional[Beatmap] = None

        # {id: {'callback', func, 'timeout': unixt, 'reusable': False}, ...}
        self.menu_options: dict[int, dict[str, Any]] = {}

        # packet queue
        self._queue = queue.SimpleQueue()

    def __repr__(self) -> str:
        return f'<{self.name} ({self.id})>'

    @property
    def url(self) -> str:
        """The url to the player's profile."""
        return f'https://{glob.config.domain}/u/{self.id}'

    @property
    def embed(self) -> str:
        """An osu! chat embed to the player's profile."""
        return f'[{self.url} {self.name}]'

    @property
    def remaining_silence(self) -> int:
        """The remaining time of the players silence."""
        return max(0, int(self.silence_end - time.time()))

    @property
    def silenced(self) -> bool:
        """Whether or not the player is silenced."""
        return self.remaining_silence != 0

    @property
    def bancho_priv(self) -> int:
        """The player's privileges according to the client."""
        ret = ClientPrivileges(0)
        if self.priv & Privileges.Normal:
            # all players have in-game "supporter".
            # this enables stuff like osu!direct,
            # multiplayer in cutting edge, etc.
            ret |= (ClientPrivileges.Player | ClientPrivileges.Supporter)
        if self.priv & Privileges.Mod:
            ret |= ClientPrivileges.Moderator
        if self.priv & Privileges.Admin:
            ret |= ClientPrivileges.Developer
        if self.priv & Privileges.Dangerous:
            ret |= ClientPrivileges.Owner
        return ret

    @property
    def gm_stats(self) -> ModeData:
        """The player's stats in their currently selected mode."""
        return self.stats[self.status.mode]

    @property
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

    async def logout(self) -> None:
        """Log `self` out of the server."""

        # invalidate the user's token.
        self.token = ''

        # leave multiplayer.
        if self.match:
            await self.leave_match()

        # stop spectating.
        if h := self.spectating:
            await h.remove_spectator(self)

        # leave channels
        while self.channels:
            await self.leave_channel(self.channels[0])

        # remove from playerlist and
        # enqueue logout to all users.
        glob.players.remove(self)
        glob.players.enqueue(packets.logout(self.id))

    async def update_privs(self, new: Privileges) -> None:
        """Update `self`'s privileges to `new`."""
        self.priv = new

        await glob.db.execute(
            'UPDATE users '
            'SET priv = %s '
            'WHERE id = %s',
            [int(self.priv), self.id]
        )

    async def add_privs(self, bits: Privileges) -> None:
        """Update `self`'s privileges, adding `bits`."""
        self.priv |= bits

        await glob.db.execute(
            'UPDATE users '
            'SET priv = %s '
            'WHERE id = %s',
            [int(self.priv), self.id]
        )

    async def remove_privs(self, bits: Privileges) -> None:
        """Update `self`'s privileges, removing `bits`."""
        self.priv &= ~bits

        await glob.db.execute(
            'UPDATE users '
            'SET priv = %s '
            'WHERE id = %s',
            [int(self.priv), self.id]
        )

    async def ban(self, admin: 'Player', reason: str) -> None:
        """Ban `self` for `reason`, and log to sql."""
        self.remove_privs(Privileges.Normal)

        log_msg = f'{admin} banned for "{reason}".'
        await glob.db.execute(
            'INSERT INTO logs (`from`, `to`, `msg`, `time`) '
            'VALUES (%s, %s, %s, NOW())',
            [admin.id, self.id, log_msg]
        )

        if self in glob.players:
            # if user is online, notify and log them out.
            # XXX: if you want to lock the player's
            # client, you can send -3 rather than -1.
            self.enqueue(packets.userID(-1))
            self.enqueue(packets.notification(
                'Your account has been banned.\n\n'
                'If you believe this was a mistake or '
                'have waited >= 2 months, you can appeal '
                'using the appeal form on the website.'
            ))

        log(f'Banned {self}.', Ansi.CYAN)

    async def unban(self, admin: 'Player', reason: str) -> None:
        """Unban `self` for `reason`, and log to sql."""
        self.add_privs(Privileges.Normal)

        log_msg = f'{admin} unbanned for "{reason}".'
        await glob.db.execute(
            'INSERT INTO logs (`from`, `to`, `msg`, `time`) '
            'VALUES (%s, %s, %s, NOW())',
            [admin.id, self.id, log_msg]
        )

        log(f'Unbanned {self}.', Ansi.CYAN)

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
            'INSERT INTO logs (`from`, `to`, `msg`, `time`) '
            'VALUES (%s, %s, %s, NOW())',
            [admin.id, self.id, log_msg]
        )

        # inform the user's client
        self.enqueue(packets.silenceEnd(duration))

        # wipe their messages from any channels.
        glob.players.enqueue(packets.userSilenced(self.id))

        log(f'Silenced {self}.', Ansi.CYAN)

    async def unsilence(self, admin: 'Player') -> None:
        """Unsilence `self`, and log to sql."""
        self.silence_end = int(time.time())

        await glob.db.execute(
            'UPDATE users SET silence_end = %s WHERE id = %s',
            [self.silence_end, self.id]
        )

        log_msg = f'{admin} unsilenced.'
        await glob.db.execute(
            'INSERT INTO logs (`from`, `to`, `msg`, `time`) '
            'VALUES (%s, %s, %s, NOW())',
            [admin.id, self.id, log_msg]
        )

        # inform the user's client
        self.enqueue(packets.silenceEnd(0))

        log(f'Unsilenced {self}.', Ansi.CYAN)

    async def join_match(self, m: Match, passwd: str) -> bool:
        """Attempt to add `self` to `m`."""
        if self.match:
            log(f'{self} tried to join multiple matches?')
            self.enqueue(packets.matchJoinFail())
            return False

        if self is not m.host:
            # match already exists, we're simply joining.
            if passwd != m.passwd:
                log(f'{self} tried to join {m} with incorrect passwd.')
                self.enqueue(packets.matchJoinFail())
                return False
            if (slotID := m.get_free()) is None:
                log(f'{self} tried to join a full match.')
                self.enqueue(packets.matchJoinFail())
                return False

        else:
            # match is being created
            slotID = 0

        if not await self.join_channel(m.chat):
            log(f'{self} failed to join {m.chat}.')
            return False

        if (lobby := glob.channels['#lobby']) in self.channels:
            await self.leave_channel(lobby)

        slot = m.slots[0 if slotID == -1 else slotID]

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

    async def leave_match(self) -> None:
        """Attempt to remove `self` from their match."""
        if not self.match:
            if glob.config.debug:
                log(f"{self} tried leaving a match they're not in?")
            return

        for s in self.match.slots:
            if self == s.player:
                s.reset()
                break

        await self.leave_channel(self.match.chat)

        if all(map(lambda s: s.empty(), self.match.slots)):
            # multi is now empty, chat has been removed.
            # remove the multi from the channels list.
            log(f'Match {self.match} finished.')
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

            # notify others of our deprature
            self.match.enqueue_state()

        self.match = None

    async def join_channel(self, c: Channel) -> bool:
        """Attempt to add `self` to `c`."""
        if self in c:
            # user already in the channel.
            if glob.config.debug:
                log(f'{self} was double-added to {c}.')

            return False

        if not self.priv & c.read:
            log(f'{self} tried to join {c} but lacks privs.')
            return False

        # lobby can only be interacted with while in mp lobby.
        if c._name == '#lobby' and not self.in_lobby:
            return False

        c.append(self) # Add to channels
        self.channels.append(c) # Add to player

        self.enqueue(packets.channelJoin(c.name))

        # update channel usercounts for all clients that can see.
        # for instanced channels, enqueue update to only players
        # in the instance; for normal channels, enqueue to all.
        targets = c.players if c.instance else glob.players

        for p in targets:
            p.enqueue(packets.channelInfo(*c.basic_info))

        if glob.config.debug:
            log(f'{self} joined {c}.')

        return True

    async def leave_channel(self, c: Channel) -> None:
        """Attempt to remove `self` from `c`."""
        if self not in c:
            log(f'{self} tried to leave {c} but is not in it.')
            return

        await c.remove(self) # remove from channels
        self.channels.remove(c) # remove from player

        self.enqueue(packets.channelKick(c.name))

        # update channel usercounts for all clients that can see.
        # for instanced channels, enqueue update to only players
        # in the instance; for normal channels, enqueue to all.
        targets = c.players if c.instance else glob.players

        for p in targets:
            p.enqueue(packets.channelInfo(*c.basic_info))

        if glob.config.debug:
            log(f'{self} left {c}.')

    async def add_spectator(self, p: 'Player') -> None:
        """Attempt to add `p` to `self`'s spectators."""
        chan_name = f'#spec_{self.id}'

        if not (c := glob.channels[chan_name]):
            # spectator chan doesn't exist, create it.
            spec_chan = Channel(
                name = chan_name,
                topic = f"{self.name}'s spectator channel.'",
                read = Privileges.Normal,
                write = Privileges.Normal,
                auto_join = False,
                instance = True
            )

            glob.channels.append(spec_chan)

            c = glob.channels[chan_name]

        # attempt to join their spectator channel.
        if not await p.join_channel(c):
            return log(f'{self} failed to join {c}?')

        #p.enqueue(packets.channelJoin(c.name))
        p_joined = packets.fellowSpectatorJoined(p.id)

        for s in self.spectators:
            s.enqueue(p_joined)
            p.enqueue(packets.fellowSpectatorJoined(s.id))

        self.spectators.append(p)
        p.spectating = self

        self.enqueue(packets.spectatorJoined(p.id))
        log(f'{p} is now spectating {self}.')

    async def remove_spectator(self, p: 'Player') -> None:
        """Attempt to remove `p` from `self`'s spectators."""
        self.spectators.remove(p)
        p.spectating = None

        c = glob.channels[f'#spec_{self.id}']
        await p.leave_channel(c)

        if not self.spectators:
            # remove host from channel, deleting it.
            await self.leave_channel(c)
        else:
            fellow = packets.fellowSpectatorLeft(p.id)
            c_info = packets.channelInfo(*c.basic_info) # new playercount

            self.enqueue(c_info)

            for s in self.spectators:
                s.enqueue(fellow + c_info)

        self.enqueue(packets.spectatorLeft(p.id))
        log(f'{p} is no longer spectating {self}.')

    async def add_friend(self, p: 'Player') -> None:
        """Attempt to add `p` to `self`'s friends."""
        if p.id in self.friends:
            log(f'{self} tried to add {p}, who is already their friend!')
            return

        self.friends.add(p.id)
        await glob.db.execute(
            'INSERT INTO friendships '
            'VALUES (%s, %s)',
            [self.id, p.id])

        log(f'{self} added {p} to their friends.')

    async def remove_friend(self, p: 'Player') -> None:
        """Attempt to remove `p` from `self`'s friends."""
        if not p.id in self.friends:
            log(f'{self} tried to remove {p}, who is not their friend!')
            return

        self.friends.remove(p.id)
        await glob.db.execute(
            'DELETE FROM friendships '
            'WHERE user1 = %s AND user2 = %s',
            [self.id, p.id])

        log(f'{self} removed {p} from their friends.')

    def queue_empty(self) -> bool:
        """Whether or not `self`'s packet queue is empty."""
        return self._queue.empty()

    def enqueue(self, b: bytes) -> None:
        """Add data to be sent to the client."""
        self._queue.put_nowait(b)

    def dequeue(self) -> Optional[bytes]:
        """Get data from the queue to send to the client."""
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            pass

    async def send(self, client: 'Player', msg: str,
                   chan: Optional[Channel] = None) -> None:
        """Enqueue `client`'s `msg` to `self`. Sent in `chan`, or dm."""
        self.enqueue(
            packets.sendMessage(
                client = client.name,
                msg = msg,
                target = (chan or self).name,
                client_id = client.id
            )
        )

    async def fetch_geoloc(self, ip: str) -> None:
        """Fetch a player's geolocation data based on their ip."""
        url = f'http://ip-api.com/json/{ip}'

        async with glob.http.get(url) as resp:
            if not resp or resp.status != 200:
                log('Failed to get geoloc data: request failed.', Ansi.LRED)
                return

            res = await resp.json()

        if 'status' not in res or res['status'] != 'success':
            log(f"Failed to get geoloc data: {res['message']}.", Ansi.LRED)
            return

        country = res['countryCode']

        # store their country as a 2-letter code, and as a number.
        # the players location is stored for the ingame world map.
        self.country = (country_codes[country], country)
        self.location = (res['lon'], res['lat'])

    async def update_stats(self, mode: GameMode = GameMode.vn_std) -> None:
        """Update a player's stats in-game and in sql."""
        table = mode.sql_table

        res = await glob.db.fetchall(
            f'SELECT s.pp, s.acc FROM {table} s '
            'LEFT JOIN maps m ON s.map_md5 = m.md5 '
            'WHERE s.userid = %s AND s.mode = %s '
            'AND s.status = 2 AND m.status IN (1, 2) '
            'ORDER BY s.pp DESC LIMIT 100',
            [self.id, mode.as_vanilla]
        )

        if not res:
            return # ?

        stats = self.stats[mode]

        # increment playcount
        stats.plays += 1

        # calculate avg acc based on top 50 scores
        stats.acc = sum([row['acc'] for row in res[:50]]) / min(50, len(res))

        # calculate weighted pp based on top 100 scores
        stats.pp = round(sum(row['pp'] * 0.95 ** i for i, row in enumerate(res)))

        # keep stats up to date in sql
        await glob.db.execute(
            'UPDATE stats SET pp_{0:sql} = %s, '
            'plays_{0:sql} = plays_{0:sql} + 1, '
            'acc_{0:sql} = %s WHERE id = %s'.format(mode),
            [stats.pp, stats.acc, self.id]
        )

        # calculate rank.
        res = await glob.db.fetch(
            'SELECT COUNT(*) AS c FROM stats '
            'LEFT JOIN users USING(id) '
            f'WHERE pp_{mode:sql} > %s '
            'AND priv & 1',
            [stats.pp]
        )

        stats.rank = res['c'] + 1
        self.enqueue(packets.userStats(self))

    async def friends_from_sql(self) -> None:
        """Retrieve `self`'s friends from sql."""
        _friends = {row['user2'] async for row in glob.db.iterall(
            'SELECT user2 FROM friendships WHERE user1 = %s', [self.id]
        )}

        # always have self & bot added to friends.
        self.friends = _friends | {1, self.id}

    async def stats_from_sql_full(self) -> None:
        """Retrieve `self`'s stats (all modes) from sql."""
        for mode in GameMode:
            # grab static stats from SQL.
            res = await glob.db.fetch(
                'SELECT tscore_{0:sql} tscore, rscore_{0:sql} rscore, '
                'pp_{0:sql} pp, plays_{0:sql} plays, acc_{0:sql} acc, '
                'playtime_{0:sql} playtime, maxcombo_{0:sql} max_combo '
                'FROM stats WHERE id = %s'.format(mode),
                [self.id]
            )

            if not res:
                log(f"Failed to fetch {self}'s {mode!r} stats.", Ansi.LRED)
                return

            # calculate rank.
            res['rank'] = (await glob.db.fetch(
                'SELECT COUNT(*) AS c FROM stats '
                'LEFT JOIN users USING(id) '
                f'WHERE pp_{mode:sql} > %s '
                'AND priv & 1', [res['pp']]
            ))['c'] + 1

            # update stats
            self.stats[mode] = ModeData(**res)

    async def stats_from_sql(self, mode: GameMode) -> None:
        """Retrieve `self`'s `mode` stats from sql."""
        res = await glob.db.fetch(
            'SELECT tscore_{0:sql} tscore, rscore_{0:sql} rscore, '
            'pp_{0:sql} pp, plays_{0:sql} plays, acc_{0:sql} acc, '
            'playtime_{0:sql} playtime, maxcombo_{0:sql} max_combo '
            'FROM stats WHERE id = %s'.format(mode),
            [self.id]
        )

        if not res:
            log(f"Failed to fetch {self}'s {mode!r} stats.", Ansi.LRED)
            return

        # calculate rank.
        res['rank'] = await glob.db.fetch(
            'SELECT COUNT(*) AS c FROM stats '
            'LEFT JOIN users USING(id) '
            f'WHERE pp_{mode:sql} > %s '
            'AND priv & 1',
            [res['pp']]
        )['c']

        self.stats[mode] = ModeData(**res)

    async def add_to_menu(self, coroutine: Coroutine,
                          timeout: int = -1, reusable: bool = False
                         ) -> None:
        """Add a valid callback to the user's osu! chat options."""
        # generate random negative number in int32 space as the key.
        rand = partial(random.randint, -0x80000000, 0)
        while (randnum := rand()) in self.menu_options:
            ...

        # append the callback to their menu options w/ args.
        self.menu_options |= {
            randnum: {
                'callback': coroutine,
                'reusable': reusable,
                'timeout': timeout if timeout != -1 else 0x7fffffff
            }
        }

        # return the key.
        return randnum
