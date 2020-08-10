# -*- coding: utf-8 -*-

from typing import Dict, Final, Optional
from random import choices
from requests import get as req_get
from string import ascii_lowercase
from time import time
from json import loads

from constants.privileges import Privileges, BanchoPrivileges
from console import printlog, Ansi

from objects.channel import Channel
from objects.match import Match, SlotStatus
from objects import glob
from enum import IntEnum
from queue import SimpleQueue
import packets

__all__ = (
    'ModeData',
    'GameMode',
    'Status',
    'Player'
)

countryCodes: Final[Dict[str, int]] = { # Talk about ugly lol
    'XX':  0,  'OC':   1, 'EU':   2, 'AD':   3, 'AE':   4, 'AF':   5, 'AG':   6, 'AI':   7, 'AL':   8, 'AM':   9, 'AN':  10,
    'AO':  11, 'AQ':  12, 'AR':  13, 'AS':  14, 'AT':  15, 'AU':  16, 'AW':  17, 'AZ':  18, 'BA':  19, 'BB':  20, 'BD':  21,
    'BE':  22, 'BF':  23, 'BG':  24, 'BH':  25, 'BI':  26, 'BJ':  27, 'BM':  28, 'BN':  29, 'BO':  30, 'BR':  31, 'BS':  32,
    'BT':  33, 'BV':  34, 'BW':  35, 'BY':  36, 'BZ':  37, 'CA':  38, 'CC':  39, 'CD':  40, 'CF':  41, 'CG':  42, 'CH':  43,
    'CI':  44, 'CK':  45, 'CL':  46, 'CM':  47, 'CN':  48, 'CO':  49, 'CR':  50, 'CU':  51, 'CV':  52, 'CX':  53, 'CY':  54,
    'CZ':  55, 'DE':  56, 'DJ':  57, 'DK':  58, 'DM':  59, 'DO':  60, 'DZ':  61, 'EC':  62, 'EE':  63, 'EG':  64, 'EH':  65,
    'ER':  66, 'ES':  67, 'ET':  68, 'FI':  69, 'FJ':  70, 'FK':  71, 'FM':  72, 'FO':  73, 'FR':  74, 'FX':  75, 'GA':  76,
    'GB':  77, 'GD':  78, 'GE':  79, 'GF':  80, 'GH':  81, 'GI':  82, 'GL':  83, 'GM':  84, 'GN':  85, 'GP':  86, 'GQ':  87,
    'GR':  88, 'GS':  89, 'GT':  90, 'GU':  91, 'GW':  92, 'GY':  93, 'HK':  94, 'HM':  95, 'HN':  96, 'HR':  97, 'HT':  98,
    'HU':  99, 'ID': 100, 'IE': 101, 'IL': 102, 'IN': 103, 'IO': 104, 'IQ': 105, 'IR': 106, 'IS': 107, 'IT': 108, 'JM': 109,
    'JO': 110, 'JP': 111, 'KE': 112, 'KG': 113, 'KH': 114, 'KI': 115, 'KM': 116, 'KN': 117, 'KP': 118, 'KR': 119, 'KW': 120,
    'KY': 121, 'KZ': 122, 'LA': 123, 'LB': 124, 'LC': 125, 'LI': 126, 'LK': 127, 'LR': 128, 'LS': 129, 'LT': 130, 'LU': 131,
    'LV': 132, 'LY': 133, 'MA': 134, 'MC': 135, 'MD': 136, 'MG': 137, 'MH': 138, 'MK': 139, 'ML': 140, 'MM': 141, 'MN': 142,
    'MO': 143, 'MP': 144, 'MQ': 145, 'MR': 146, 'MS': 147, 'MT': 148, 'MU': 149, 'MV': 150, 'MW': 151, 'MX': 152, 'MY': 153,
    'MZ': 154, 'NA': 155, 'NC': 156, 'NE': 157, 'NF': 158, 'NG': 159, 'NI': 160, 'NL': 161, 'NO': 162, 'NP': 163, 'NR': 164,
    'NU': 165, 'NZ': 166, 'OM': 167, 'PA': 168, 'PE': 169, 'PF': 170, 'PG': 171, 'PH': 172, 'PK': 173, 'PL': 174, 'PM': 175,
    'PN': 176, 'PR': 177, 'PS': 178, 'PT': 179, 'PW': 180, 'PY': 181, 'QA': 182, 'RE': 183, 'RO': 184, 'RU': 185, 'RW': 186,
    'SA': 187, 'SB': 188, 'SC': 189, 'SD': 190, 'SE': 191, 'SG': 192, 'SH': 193, 'SI': 194, 'SJ': 195, 'SK': 196, 'SL': 197,
    'SM': 198, 'SN': 199, 'SO': 200, 'SR': 201, 'ST': 202, 'SV': 203, 'SY': 204, 'SZ': 205, 'TC': 206, 'TD': 207, 'TF': 208,
    'TG': 209, 'TH': 210, 'TJ': 211, 'TK': 212, 'TM': 213, 'TN': 214, 'TO': 215, 'TL': 216, 'TR': 217, 'TT': 218, 'TV': 219,
    'TW': 220, 'TZ': 221, 'UA': 222, 'UG': 223, 'UM': 224, 'US': 225, 'UY': 226, 'UZ': 227, 'VA': 228, 'VC': 229, 'VE': 230,
    'VG': 231, 'VI': 232, 'VN': 233, 'VU': 234, 'WF': 235, 'WS': 236, 'YE': 237, 'YT': 238, 'RS': 239, 'ZA': 240, 'ZM': 241,
    'ME': 242, 'ZW': 243, 'XX': 244, 'A2': 245, 'O1': 246, 'AX': 247, 'GG': 248, 'IM': 249, 'JE': 250, 'BL': 251, 'MF': 252
}

class ModeData:
    """A class to represent a player's stats in a single gamemode.

    Attributes
    -----------
    tscore: :class:`int`
        The player's total score.

    rscore: :class:`int`
        The player's ranked score.

    pp: :class:`float`
        The player's total performance points.

    playcount: :class:`int`
        The player's playcount.

    acc: :class:`float`
        The player's overall accuracy.

    rank: :class:`int`
        The player's global rank.

    max_combo: :class:`int`
        The player's highest combo.
    """
    __slots__ = (
        'tscore', 'rscore', 'pp', 'playcount',
        'acc', 'rank', 'max_combo'
    )

    def __init__(self):
        self.tscore = 0
        self.rscore = 0
        self.pp = 0
        self.playcount = 0
        self.acc = 0.0
        self.rank = 0
        self.max_combo = 0

    def update(self, **kwargs) -> None:
        self.tscore = kwargs.get('tscore', 0)
        self.rscore = kwargs.get('rscore', 0)
        self.pp = kwargs.get('pp', 0)
        self.playcount = kwargs.get('playcount', 0)
        self.acc = kwargs.get('acc', 0.0)
        self.rank = kwargs.get('rank', 0)
        self.max_combo = kwargs.get('max_combo', 0)

class GameMode(IntEnum):
    """A class to represent a gamemode."""

    # This is another place where some
    # inspiration was taken from rumoi/ruri.
    vn_std = 0
    vn_taiko = 1
    vn_catch = 2
    vn_mania = 3
    rx_std = 4
    rx_taiko = 5
    rx_catch = 6

    def __str__(self) -> str:
        return {
            0: 'vn!std',
            1: 'vn!taiko',
            2: 'vn!catch',
            3: 'vn!mania',

            4: 'rx!std',
            5: 'rx!taiko',
            6: 'rx!catch'
        }[self.value]

    def __format__(self, format: str) -> str:
        # lmao
        return {
            0: 'vn_std',
            1: 'vn_taiko',
            2: 'vn_catch',
            3: 'vn_mania',

            4: 'rx_std',
            5: 'rx_taiko',
            6: 'rx_catch'
        }[self.value] if format == 'sql' else str(self.value)

class Status:
    """A class to represent the current status of a player.

    Attributes
    -----------
    action: :class:`int`
        The actionID of the player.
        0: Idle, 1: AFK, 2: Playing,
        3: Editing, 4: Modding, 5: Multiplayer,
        6: Watching, 7: Unknown, 8: Testing,
        9: Submitting, 10: Paused, 11: Lobby,
        12: Multiplaying, 13: osu!direct

    info_text: :class:`str`
        The text representing the user's action.

    map_md5: :class:`str`
        The md5 of the map the player is on.

    mods: :class:`int`
        The mods the player currently has enabled.

    game_mode: :class:`int`
        The current gamemode of the player.

    map_id: :class:`int`
        The id of the map the player is on.
    """
    __slots__ = (
        'action', 'info_text', 'map_md5',
        'mods', 'game_mode', 'map_id'
    )

    def __init__(self):
        self.action = 0 # byte
        self.info_text = '' # string
        self.map_md5 = '' # string
        self.mods = 0 # i32
        self.game_mode = 0 # byte
        self.map_id = 0 # i32

    def update(self, action, info_text, map_md5,
               mods, game_mode, map_id) -> None:
        self.action = action
        self.info_text = info_text
        self.map_md5 = map_md5
        self.mods = mods
        self.game_mode = game_mode
        self.map_id = map_id

class Player:
    """A class to represent a player.

    Attributes
    -----------
    token: :class:`str`
        The player's unique token; used to
        communicate with the osu! client.

    id: :class:`int`
        The player's unique ID.

    name: :class:`str`
        The player's username (unsafe).

    safe_name: :class:`str`
        The player's username (safe).
        XXX: Equivalent to `cls.name.lower().replace(' ', '_')`.

    priv: :class:`Privileges`
        The player's privileges.

    rx: :class:`bool`
        Whether the player is using rx (used for gamemodes).

    stats: List[:class:`ModeData`]
        A list of `ModeData` objs representing
        the player's stats for each gamemode.

    status: :class:`Status`
        A `Status` obj representing the player's current status.

    friends: List[:class:`int`]
        A list of player ids representing the player's friends.

    channels: List[:class:`Channel`]
        A list of `Channel` objs representing the channels the user is in.

    spectators: List[:class:`Player`]
        A list of `Player` objs representing the player's spectators.

    spectating: Optional[:class:`Player`]
        A `Player` obj representing the player this player is spectating.

    match: Optional[:class:`Match`]
        A `Match` obj representing the match the player is in.

    location: Tuple[:class:`float`, :class:`float`]
        A tuple containing the latitude and longitude of the player.

    country: Tuple[:class:`str`, :class:`int`]
        A tuple containing the country code in letter and number forms.

    utc_offset: :class:`int`
        The player's UTC offset as an integer.

    pm_private: :class:`bool`
        Whether the player is blocking pms from non-friends.

    away_msg: Optional[:class:`str`]
        A string representing the player's away message.

    silence_end: :class:`int`
        The UNIX timestamp the player's silence will end at.

    in_lobby: :class:`bool`
        Whether the player is currently in the multiplayer lobby.

    login_time: :class:`int`
        The UNIX timestamp of when the player logged in.

    ping_time: :class:`int`
        The UNIX timestamp of the last time the client pinged the server.

    _queue: :class:`SimpleQueue`
        A `SimpleQueue` obj representing our packet queue.
        XXX: cls.enqueue() will add data to this queue, and
             cls.dequeue() will return the data, and remove it.

    Properties
    -----------
    url: :class:`str`
        The user's url to their profile.

    embed: :class:`str`
        An osu! chat embed of a user's profile which displays their username.

    silenced: :class:`bool`
        Whether the user is currently silenced.

    bancho_priv: :class:`BanchoPrivileges`
        The user's privileges in the osu! client.

    gm_stats: :class:`ModeData`
        The user's stats for the current gamemode.
    """
    __slots__ = (
        'token', 'id', 'name', 'safe_name', 'priv',
        'rx', 'stats', 'status',
        'friends', 'channels', 'spectators', 'spectating', 'match',
        'recent_scores', 'country', 'location',
        'utc_offset', 'pm_private',
        'away_msg', 'silence_end', 'in_lobby',
        'login_time', 'ping_time',
        '_queue'
    )

    def __init__(self, *args, **kwargs) -> None:
        # not sure why im scared of empty kwargs?
        self.token = kwargs.get('token', ''.join(choices(ascii_lowercase, k = 32)))
        self.id = kwargs.get('id', None)
        self.name = kwargs.get('name', None)
        self.safe_name = self.ensure_safe(self.name) if self.name else None
        self.priv = Privileges(kwargs.get('priv', Privileges.Banned))

        self.rx = False # stored for ez use
        self.stats = [ModeData() for _ in range(7)]
        self.status = Status()

        self.friends = set() # userids, not player objects
        self.channels = []
        self.spectators = []
        self.spectating = None
        self.match = None

        # Store the user's most recently submitted scores for both regular and
        self.recent_scores = [None for _ in range(7)]

        self.country = (0, 'XX') # (code , letters)
        self.location = (0.0, 0.0) # (lat, long)

        self.utc_offset = kwargs.get('utc_offset', 0)
        self.pm_private = kwargs.get('pm_private', False)

        self.away_msg = None
        self.silence_end = 0
        self.in_lobby = False

        c_time = int(time())
        self.login_time = c_time
        self.ping_time = c_time
        del c_time

        # Packet queue
        self._queue = SimpleQueue()

    @property
    def url(self) -> str:
        return f'https://akatsuki.pw/u/{self.id}'

    @property
    def embed(self) -> str:
        return f'[{self.url} {self.name}]'

    @property
    def silenced(self) -> bool:
        return time() <= self.silence_end

    @property
    def bancho_priv(self) -> int:
        ret = BanchoPrivileges(0)
        if self.priv & Privileges.Verified:
            # All players have ingame "supporter".
            # This enables stuff like osu!direct,
            # multiplayer in cutting edge, etc.
            ret |= (BanchoPrivileges.Player | BanchoPrivileges.Supporter)
        if self.priv & Privileges.Mod:
            ret |= BanchoPrivileges.Moderator
        if self.priv & Privileges.Admin:
            ret |= BanchoPrivileges.Developer
        if self.priv & Privileges.Dangerous:
            ret |= BanchoPrivileges.Owner
        return ret

    @property
    def gm_stats(self) -> ModeData:
        if self.status.game_mode == 3:
            # Mania is the same mode on both vn and rx.
            return self.stats[3]

        return self.stats[self.status.game_mode + (4 if self.rx else 0)]

    def __repr__(self) -> str:
        return f'<id: {self.id} | name: {self.name}>'

    @staticmethod
    def ensure_safe(name: str) -> str:
        return name.lower().replace(' ', '_')

    def logout(self) -> None:
        # Invalidate the user's token.
        self.token = ''

        # Leave multiplayer.
        if self.match:
            self.leave_match()

        # Stop spectating.
        if h := self.spectating:
            h.remove_spectator(self)

        # Leave channels
        while self.channels:
            self.leave_channel(self.channels[0])

        # Remove from playerlist and
        # enqueue logout to all users.
        glob.players.remove(self)
        glob.players.enqueue(packets.logout(self.id))

    def restrict(self) -> None: # TODO: reason
        self.priv &= ~Privileges.Visible
        glob.db.execute(
            'UPDATE users SET priv = %s WHERE id = %s',
            [self.priv, self.id]
        )

        self.enqueue(packets.notification('Your account has been restricted.'))
        printlog(f'Restricted {self}.', Ansi.CYAN)

    def unrestrict(self) -> None:
        self.priv &= Privileges.Visible
        glob.db.execute(
            'UPDATE users SET priv = %s WHERE id = %s',
            [self.priv, self.id]
        )

        self.enqueue(packets.notification('Your account has been unrestricted.'))
        printlog(f'Unrestricted {self}.', Ansi.CYAN)

    def join_match(self, m: Match, passwd: str) -> bool:
        if self.match:
            printlog(f'{self} tried to join multiple matches?')
            self.enqueue(packets.matchJoinFail(m))
            return False

        if m.chat: # Match already exists, we're simply joining.
            if passwd != m.passwd: # eff: could add to if? or self.create_m..
                printlog(f'{self} tried to join {m} with incorrect passwd.')
                self.enqueue(packets.matchJoinFail(m))
                return False
            if (slotID := m.get_free()) is None:
                printlog(f'{self} tried to join a full match.')
                self.enqueue(packets.matchJoinFail(m))
                return False
        else:
            # Match is being created
            slotID = 0
            glob.matches.add(m) # add to global matchlist
                                # This will generate an ID.

            glob.channels.add(Channel(
                name = f'#multi_{m.id}',
                topic = f"MID {m.id}'s multiplayer channel.",
                read = Privileges.Verified,
                write = Privileges.Verified,
                auto_join = False,
                temp = True))

            m.chat = glob.channels.get(f'#multi_{m.id}')

        if not self.join_channel(m.chat):
            printlog(f'{self} failed to join {m.chat}.')
            return False

        if (lobby := glob.channels.get('#lobby')) in self.channels:
            self.leave_channel(lobby)

        slot = m.slots[0 if slotID == -1 else slotID]

        slot.status = SlotStatus.not_ready
        slot.player = self
        self.match = m
        self.enqueue(packets.matchJoinSuccess(m))
        m.enqueue(packets.updateMatch(m))

        return True

    def leave_match(self) -> None:
        if not self.match:
            printlog(f'{self} tried leaving a match but is not in one?')
            return

        for s in self.match.slots:
            if self == s.player:
                s.reset()
                break

        self.leave_channel(self.match.chat)

        if all(s.empty() for s in self.match.slots):
            # Multi is now empty, chat has been removed.
            # Remove the multi from the channels list.
            printlog(f'Match {self.match} finished.')
            glob.matches.remove(self.match)

            if (lobby := glob.channels.get('#lobby')):
                lobby.enqueue(packets.disposeMatch(self.match.id))
        else: # Notify others of our deprature
            self.match.enqueue(packets.updateMatch(self.match))

        self.match = None

    def join_channel(self, c: Channel) -> bool:
        if self in c:
            printlog(f'{self} tried to double join {c}.')
            return False

        if not self.priv & c.read:
            printlog(f'{self} tried to join {c} but lacks privs.')
            return False

        # Lobby can only be interacted with while in mp lobby.
        if c._name == '#lobby' and not self.in_lobby:
            return False

        c.append(self) # Add to channels
        self.channels.append(c) # Add to player

        self.enqueue(packets.channelJoin(c.name))
        printlog(f'{self} joined {c}.')
        return True

    def leave_channel(self, c: Channel) -> None:
        if self not in c:
            printlog(f'{self} tried to leave {c} but is not in it.')
            return

        c.remove(self) # Remove from channels
        self.channels.remove(c) # Remove from player

        self.enqueue(packets.channelKick(c.name))
        printlog(f'{self} left {c}.')

    def add_spectator(self, p) -> None:
        self.spectators.append(p)
        p.spectating = self

        fellow = packets.fellowSpectatorJoined(p.id)

        chan_name = f'#spec_{self.id}'
        if not (c := glob.channels.get(chan_name)):
            # Spec channel does not exist, create it and join.
            glob.channels.add(Channel(
                name = chan_name,
                topic = f"{self.name}'s spectator channel.'",
                read = Privileges.Verified,
                write = Privileges.Verified,
                auto_join = False,
                temp = True))

            c = glob.channels.get(chan_name)

        if not p.join_channel(c):
            return printlog(f'{self} failed to join {c}?')

        p.enqueue(packets.channelJoin(c.name))

        for s in self.spectators:
            self.enqueue(fellow) # #spec?
            s.enqueue(packets.fellowSpectatorJoined(self.id))

        self.enqueue(packets.spectatorJoined(p.id))

        printlog(f'{p} is now spectating {self}.')

    def remove_spectator(self, p) -> None:
        self.spectators.remove(p)
        p.spectating = None

        c = glob.channels.get(f'#spec_{self.id}')
        p.leave_channel(c)

        if not self.spectators:
            # Remove host from channel, deleting it.
            self.leave_channel(c)
        else:
            fellow = packets.fellowSpectatorLeft(p.id)
            c_info = packets.channelInfo(*c.basic_info) # new playercount

            self.enqueue(c_info)

            for t in self.spectators:
                t.enqueue(fellow + c_info)

        self.enqueue(packets.spectatorLeft(p.id))
        printlog(f'{p} is no longer spectating {self}.')

    def add_friend(self, p) -> None:
        if p.id in self.friends:
            printlog(f'{self} tried to add {p}, who is already their friend!')
            return

        self.friends.add(p.id)
        glob.db.execute(
            'INSERT INTO friendships '
            'VALUES (%s, %s)',
            [self.id, p.id])

        printlog(f'{self} added {p} to their friends.')

    def remove_friend(self, p) -> None:
        if not p.id in self.friends:
            printlog(f'{self} tried to remove {p}, who is not their friend!')
            return

        self.friends.remove(p.id)
        glob.db.execute(
            'DELETE FROM friendships '
            'WHERE user1 = %s AND user2 = %s',
            [self.id, p.id])

        printlog(f'{self} removed {p} from their friends.')

    def queue_empty(self) -> bool:
        return self._queue.empty()

    def enqueue(self, b: bytes) -> None:
        self._queue.put_nowait(b)

    def dequeue(self) -> bytes:
        try:
            return self._queue.get_nowait()
        except:
            printlog('Empty queue?')

    def fetch_geoloc(self, ip: str) -> None:
        if not (res := req_get(f'http://ip-api.com/json/{ip}')):
            printlog('Failed to get geoloc data: request failed.', Ansi.LIGHT_RED)
            return

        res = res.json()

        if 'status' not in res or res['status'] != 'success':
            printlog(f"Failed to get geoloc data: {res['message']}.", Ansi.LIGHT_RED)
            return

        country = res['countryCode']

        self.country = (countryCodes[country], country)
        self.location = (res['lat'], res['lon'])

    def update_stats(self, gm: int = GameMode.vn_std) -> None:
        table = 'scores_rx' if gm >= 4 else 'scores_vn'
        mode = GameMode(gm)

        res = glob.db.fetchall(
            f'SELECT s.pp, s.acc FROM {table} s '
            'LEFT JOIN maps m ON s.map_md5 = m.md5 '
            'WHERE s.userid = %s AND s.game_mode = %s '
            'AND s.status = 2 AND m.status IN (1, 2) '
            'ORDER BY s.pp DESC LIMIT 100', [
                self.id, gm - (4 if gm >= 4 else 0)
            ]
        )

        if not res:
            return # ?

        # Update the user's stats ingame, then update db.
        self.stats[gm].pp = sum(round(round(row['pp']) * 0.95 ** i)
                                for i, row in enumerate(res))
        self.stats[gm].acc = sum([row['acc'] for row in res][:50]) / min(50, len(res)) / 100.0

        glob.db.execute(
            f'UPDATE stats SET pp_{mode:sql} = %s, '
            f'acc_{mode:sql} = %s WHERE id = %s', [
                self.stats[gm].pp,
                self.stats[gm].acc,
                self.id
            ]
        )

        # TODO: finish off other stat related stuff

        printlog(f"Updated {self}'s {mode} stats.")

    def friends_from_sql(self) -> None:
        res = glob.db.fetchall(
            'SELECT user2 FROM friendships WHERE user1 = %s',
            [self.id])

        # Always include self and Aika on friends list.
        self.friends = {1, self.id} | {i['user2'] for i in res}

    def stats_from_sql_full(self) -> None:
        for gm in GameMode:
            if not (res := glob.db.fetch(
                'SELECT tscore_{0:sql} tscore, rscore_{0:sql} rscore, '
                'pp_{0:sql} pp, playcount_{0:sql} playcount, acc_{0:sql} acc, '
                'maxcombo_{0:sql} FROM stats WHERE id = %s'.format(gm), [self.id])
            ): raise Exception(f"Failed to fetch {self}'s {gm} user stats.")

            self.stats[gm].update(**res)

    def stats_from_sql(self: int, gm: int) -> None:
        if not (res := glob.db.fetch(
            'SELECT tscore_{0:sql} tscore, rscore_{0:sql} rscore, '
            'pp_{0:sql} pp, playcount_{0:sql} playcount, acc_{0:sql} acc, '
            'maxcombo_{0:sql} FROM stats WHERE id = %s'.format(gm), [self.id])
        ): raise Exception(f"Failed to fetch {self}'s {gm} user stats.")

        self.stats[gm].update(**res)
