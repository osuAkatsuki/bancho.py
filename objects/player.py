from random import choices
from string import ascii_lowercase
from constants import Privileges, BanchoPrivileges
import config

class ModeData:
    def __init__(self):
        self.total_score = 0
        self.ranked_score = 0
        self.pp = 0
        self.play_count = 0
        self.acc = 0.0
        self.rank = 0
        self.max_combo = 0

class Stats:
    def __init__(self):
        self.vanilla = [ModeData] * 4
        self.relax = [ModeData] * 3

    def from_sql(self, ID: int) -> None:
        if not (res := config.db.execute(
            'SELECT '
        )):
            pass

class Status:
    def __init__(self):
        self.action = None
        self.info_text = None
        self.beatmap_md5 = None
        self.mods = None
        self.game_mode = None
        self.beatmap = None

class Player:
    def __init__(self, *args, **kwargs) -> None:
        # not sure why im scared of empty kwargs?
        self.token = kwargs.get('token', ''.join(choices(ascii_lowercase, k = 32)))
        self.id = kwargs.get('id', None)
        self.name = kwargs.get('name', None)
        self.safe_name = self.ensure_safe(self.name) if self.name else None
        self.priv = Privileges(kwargs.get('priv', Privileges.Banned))

        self.stats = Stats()
        self.status = Status()
        self.channels = []

        self.country = kwargs.get('country', None)
        self.utc_offset = kwargs.get('utc_offset', 0)
        self.pm_private = kwargs.get('pm_private', False)

        self.ping_time = 0

    def join_channel(self, chan) -> None:
        print(f'{self.name} ({self.id}) joined {chan.name}.')
        self.channels.append(chan)

    def leave_channel(self, chan) -> None:
        print(f'{self.name} ({self.id}) left {chan.name}.')
        self.channels.remove(chan)

    @staticmethod
    def ensure_safe(name: str) -> str:
        return name.lower().replace(' ', '_')

    @property
    def bancho_priv(self) -> int:
        ret = BanchoPrivileges(0)
        if self.priv & Privileges.Verified:
            ret |= BanchoPrivileges.Player
        if self.priv & (Privileges.Supporter | Privileges.Premium):
            ret |= BanchoPrivileges.Supporter
        if self.priv & Privileges.Mod:
            ret |= BanchoPrivileges.Moderator
        if self.priv & Privileges.Admin:
            ret |= BanchoPrivileges.Developer
        if self.priv & Privileges.Dangerous:
            ret |= BanchoPrivileges.Owner
        return ret

class PlayerManager:
    def __init__(self):
        self.players = []

    def get(self, token: str) -> Player:
        for p in self.players: # might copy
            if p.token == token:
                return p

    def get_by_id(self, id: int) -> Player:
        for p in self.players: # might copy
            if p.id == id:
                return p

    def add(self, p: Player) -> None: # bool ret success?
        if p in self.players:
            print(f'{p.name} ({p.id}) already in players list!')
            return
        print(f'Adding {p.name} ({p.id}) to players list.')
        self.players.append(p)

    def remove(self, p: Player) -> None:
        print(f'Removing {p.name} ({p.id}) from players list.')
        self.players.remove(p)
