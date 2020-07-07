# -*- coding: utf-8 -*-

from typing import Tuple
from random import choices
from string import ascii_lowercase
from time import time

from constants.privileges import Privileges, BanchoPrivileges
from console import printlog

from objects.channel import Channel
from objects.match import Match, SlotStatus
from objects import glob
from enum import IntEnum
from queue import SimpleQueue
import packets

class ModeData:
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
    # This is another place where some
    # inspiration was taken from rumoi/ruri.
    vn_std = 0,
    vn_taiko = 1,
    vn_catch = 2,
    vn_mania = 3,
    rx_std = 4,
    rx_taiko = 5,
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
    def __init__(self):
        self.action = 0 # byte
        self.info_text = '' # string
        self.beatmap_md5 = '' # string
        self.mods = 0 # i32
        self.game_mode = 0 # byte
        self.beatmap_id = 0 # i32

    def update(self, action, info_text, beatmap_md5,
               mods, game_mode, beatmap_id) -> None:
        self.action = action
        self.info_text = info_text
        self.beatmap_md5 = beatmap_md5
        self.mods = mods
        self.game_mode = game_mode
        self.beatmap_id = beatmap_id

class Player:
    def __init__(self, *args, **kwargs) -> None:
        # not sure why im scared of empty kwargs?
        self.token = kwargs.get('token', ''.join(choices(ascii_lowercase, k = 32)))
        self.id = kwargs.get('id', None)
        self.name = kwargs.get('name', None)
        self.safe_name = self.ensure_safe(self.name) if self.name else None
        self.priv = Privileges(kwargs.get('priv', Privileges.Banned))

        self.rx = False # stored for ez use
        self.stats = [ModeData() for i in range(7)]
        self.status = Status()

        self.friends = [] # userids, not player objects
        self.channels = []
        self.spectators = []
        self.spectating = None
        self.match = None

        # TODO: countries
        self.country = 38
        self.utc_offset = kwargs.get('utc_offset', 0)
        self.pm_private = kwargs.get('pm_private', False)

        # Packet queue
        self._queue = SimpleQueue()

        self.away_message = None
        self.silence_end = 0
        self.in_lobby = False

        c_time = int(time())
        self.login_time = c_time
        self.ping_time = c_time
        del c_time

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
        if self.status.game_mode == 3 and self.rx:
            return self.stats[3] # rx mania == vn mania

        return self.stats[self.status.game_mode + (4 if self.rx else 0)]

    def __repr__(self) -> str:
        return f'<id: {self.id} | name: {self.name}>'

    def logout(self) -> None:
        # Invalidate the user's token.
        self.token = ''

        for c in self.channels:
            self.leave_channel(c)

        glob.players.remove(self)
        glob.players.enqueue(packets.logout(self.id), {self})

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
            printlog(f'{self}) tried to leave {c} but is not in it.')
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

        self.friends.append(p.id)
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

    @staticmethod
    def ensure_safe(name: str) -> str:
        return name.lower().replace(' ', '_')

    def query_info(self) -> None:
        # This is to be ran at login to cache
        # some general information on users
        # (such as stats, friends, etc.).
        self.stats_from_sql_full()
        self.friends_from_sql()

    def friends_from_sql(self) -> None:
        res = glob.db.fetchall(
            'SELECT user2 FROM friendships WHERE user1 = %s',
            [self.id])

        # Always include self and Aika on friends list.
        self.friends = [1, self.id] + [i['user2'] for i in res]

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
