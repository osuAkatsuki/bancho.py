# -*- coding: utf-8 -*-

from typing import Tuple
from random import choices
from string import ascii_lowercase
from constants.privileges import Privileges, BanchoPrivileges
from console import printlog

from objects import glob
from enum import IntEnum
from queue import SimpleQueue

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

        self.channels = []
        self.spectators = []
        self.spectating = None

        self.country = 38#self.country = kwargs.get('country', None)
        self.utc_offset = kwargs.get('utc_offset', 0)
        self.pm_private = kwargs.get('pm_private', False)

        # Packet queue
        self._queue = SimpleQueue()

        self.ping_time = 0

    def __repr__(self) -> str:
        return f'<{self.name} | {self.id}>'

    @property
    def gm_stats(self) -> ModeData:
        if self.status.game_mode == 3 and self.rx:
            return self.stats[3] # rx mania == vn mania

        return self.stats[self.status.game_mode + (4 if self.rx else 0)]

    def join_channel(self, chan) -> bool:
        if self in chan:
            printlog(f'{self} tried to double join {chan.name}.')
            return False

        if not self.priv & chan.read:
            printlog(f'{self} tried to join {chan.name} but lacks privs.')
            return False

        chan.append(self) # Add to channels
        self.channels.append(chan) # Add to player
        printlog(f'{self} joined {chan.name}.')
        return True

    def leave_channel(self, chan) -> None:
        if self not in chan:
            printlog(f'{self}) tried to leave {chan.name} but is not in it.')
            return

        chan.remove(self) # Remove from channels
        self.channels.remove(chan) # Remove from player
        printlog(f'{self} left {chan.name}.')

    def add_spectator(self, p) -> None:
        self.spectators.append(p)
        printlog(f'{p} is now spectating {self}.')

    def remove_spectator(self, p) -> None:
        self.spectators.remove(p)
        printlog(f'{p} is no longer spectating {self}.')

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

    ##
    ### User stats
    ##

    def stats_from_sql_full(self) -> None:
        for gm in GameMode:
            if not (res := glob.db.fetch(
                'SELECT tscore_{0:sql} tscore, rscore_{0:sql} rscore, '
                'pp_{0:sql} pp, playcount_{0:sql} playcount, acc_{0:sql} acc, '
                'maxcombo_{0:sql} FROM stats WHERE id = %s'.format(gm), [self.id])
            ): raise Exception(f"Failed to fetch {self.id}'s {gm!s} user stats.")

            self.stats[gm].update(**res)

    def stats_from_sql(self, id: int, gm: int) -> None:
        if not (res := glob.db.fetch(
            'SELECT tscore_{0:sql} tscore, rscore_{0:sql} rscore, '
            'pp_{0:sql} pp, playcount_{0:sql} playcount, acc_{0:sql} acc, '
            'maxcombo_{0:sql} FROM stats WHERE id = %s'.format(gm), [id])
        ): raise Exception(f"Failed to fetch {id}'s {gm} user stats.")

        self.stats[gm].update(**res)
