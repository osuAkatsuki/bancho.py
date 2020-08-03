
from typing import Final
from enum import IntEnum, unique
from time import time
from py3rijndael import RijndaelCbc, ZeroPadding
from base64 import b64decode
from constants.mods import Mods
from constants.clientflags import ClientFlags

__all__ = (
    'Rank',
    'Score'
)

@unique
class Rank(IntEnum):
    XH: Final[int] = 0
    SH: Final[int] = 1
    X:  Final[int] = 2
    S:  Final[int] = 3
    A:  Final[int] = 4
    B:  Final[int] = 5
    C:  Final[int] = 6
    D:  Final[int] = 7
    F:  Final[int] = 8

    def __str__(self) -> str:
        return {
            XH: 'SS',
            SH: 'SS',
            X: 'S',
            S: 'S',
            A: 'A',
            B: 'B',
            C: 'C',
            D: 'D',
            F: 'F'
        }[self.value]

class Score:
    __slots__ = (
        'id',
        'pp', 'score', 'max_combo', 'mods',
        'n300', 'n100', 'n50', 'nmiss', 'ngeki', 'nkatu', 'rank',
        'passed', 'perfect',
        'game_mode', 'play_time',
        'client_flags'
    )

    @classmethod
    def from_submission(cls, data_enc: str, iv: str, osu_ver: str) -> None:
        """Create a score object from an osu! submission string."""
        aes_key = f'osu!-scoreburgr---------{osu_ver}'
        cbc = RijndaelCbc(
            f'osu!-scoreburgr---------{osu_ver}',
            iv = b64decode(iv).decode('latin_1'),
            padding = ZeroPadding(32), block_size =  32
        )

        data = cbc.decrypt(b64decode(data_enc).decode('latin_1')).decode().split(':')

        if len(data) != 18:
            print('Invalid score len?')
            return None

        x = cls()
        # 0: filemd5
        # 1: playername
        # 2: online score checksum
        # 3: c300
        x.n300 = data[3].isnumeric() and int(data[3])
        # 4: c100
        x.n100 = data[4].isnumeric() and int(data[4])
        # 5: c50
        x.n50 = data[5].isnumeric() and int(data[5])
        # 6: cgeki
        x.ngeki = data[6].isnumeric() and int(data[6])
        # 7: ckatu
        x.nkatu = data[7].isnumeric() and int(data[7])
        # 8: cmiss
        x.nmiss = data[8].isnumeric() and int(data[8])
        # 9: score
        x.score = data[9].isnumeric() and int(data[9])
        # 10: maxcombo
        x.max_combo = data[10].isnumeric() and int(data[10])
        # 11: fc ('1'/'0')
        x.perfect = data[11] == '1'
        # 12: rank
        x.rank = data[12] # letter grade
        # 13: mods
        x.mods = data[13].isnumeric() and int(data[13])
        # 14: passed ('True'/'False')
        x.passed = data[14] == 'True'
        # 15: gamemode
        x.game_mode = data[15].isnumeric() and int(data[15])
        # 16: playdateTime (yyMMddHHmmss)
        x.play_time = time() # no reason to use theirs really
        # 17: osu version & anticheat with count(data[17], '\x17') lol
        x.client_flags = data[17].count(' ')

        return x

    def __init__(self):
        self.id = 0

        self.pp = 0.0
        self.score = 0
        self.max_combo = 0
        self.mods = Mods.NOMOD

        self.n300 = 0
        self.n100 = 0
        self.n50 = 0
        self.nmiss = 0
        self.ngeki = 0
        self.nkatu = 0
        self.rank = Rank.F

        self.passed = False
        self.perfect = False

        self.game_mode = 0
        self.play_time = 0

        # osu!'s client 'anticheat'.
        self.client_flags = ClientFlags.Clean

    @property
    def accuracy(self) -> float:
        # TODO calculate accuracy
        return 0.00
