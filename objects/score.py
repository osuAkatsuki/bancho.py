from enum import IntEnum, unique
from constants.mods import Mods
from constants.clientflags import ClientFlags

@unique
class Rank(IntEnum):
    XH = 0
    SH = 1
    X = 2
    S = 3
    A = 4
    B = 5
    C = 6
    D = 7
    F = 8

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
