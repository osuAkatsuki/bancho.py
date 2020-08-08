
from typing import Final, Tuple
from enum import IntEnum, unique
from time import time
from py3rijndael import RijndaelCbc, ZeroPadding
from base64 import b64decode
from pp.owoppai import Owoppai
from constants.mods import Mods
from constants.clientflags import ClientFlags

from objects import glob

__all__ = (
    'Rank',
    'SubmissionStatus',
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

@unique
class SubmissionStatus(IntEnum):
    # TODO: make a system more like bancho's?
    FAILED = 0
    SUBMITTED = 1
    BEST = 2

    def __str__(self) -> str:
        return {
            FAILED: 'Failed',
            SUBMITTED: 'Submitted',
            BEST: 'Best'
        }[self.value]

class Score:
    """A class to represent a score.

    Attributes
    -----------
    id: :class:`int`
        The score's unique ID.

    map_md5: :class:`str`
        The md5 hash of the .osu file.

    map_id: :class:`int`
        The map's unique ID.

    player: Optional[:class:`Player`]
        A player obj of the player who submitted the score.

    pp: :class:`float`
        The score's performance points.

    score: :class:`int`
        The score's osu! score value.

    max_combo: :class:`int`
        The maximum combo reached in the score.

    mods: :class:`int`
        A bitwise value of the osu! mods used in the score.

    acc: :class:`float`
        The accuracy of the score.

    n300: :class:`int`
        The number of 300s in the score.

    n100: :class:`int`
        The number of 100s in the score (150s if taiko).

    n50: :class:`int`
        The number of 50s in the score.

    nmiss: :class:`int`
        The number of misses in the score.

    ngeki: :class:`int`
        The number of gekis in the score.

    nkatu: :class:`int`
        The number of katus in the score.

    grade: :class:`str`
        The letter grade in the score.

    rank: :class:`int`
        The leaderboard placement of the score.

    passed: :class:`bool`
        Whether the score completed the map.

    perfect: :class:`bool`
        Whether the score is a full-combo.

    status: :class:`SubmissionStatus`
        The submission status of the score.

    game_mode: :class:`int`
        The game mode of the score.

    play_time: :class:`int`
        A UNIX timestamp of the time of score submission.

    client_flags: :class:`int`
        osu!'s old anticheat flags.
    """
    __slots__ = (
        'id', 'map_md5', 'map_id', 'player',
        'pp', 'score', 'max_combo', 'mods',
        'acc', 'n300', 'n100', 'n50', 'nmiss', 'ngeki', 'nkatu', 'grade',
        'rank', 'passed', 'perfect', 'status',
        'game_mode', 'play_time',
        'client_flags'
    )

    def __init__(self):
        self.id = 0

        # TODO: maaaaaaaybe beatmap class?
        # somewhat reluctant on this one.
        self.map_md5 = ''
        self.map_id = 0

        self.player = None

        self.pp = 0.0
        self.score = 0
        self.max_combo = 0
        self.mods = Mods.NOMOD

        self.acc = 0.0
        # TODO: perhaps abstract these differently
        # since they're mode dependant? feels weird..
        self.n300 = 0
        self.n100 = 0 # n150 for taiko
        self.n50 = 0
        self.nmiss = 0
        self.ngeki = 0
        self.nkatu = 0
        self.grade = Rank.F

        self.rank = 0
        self.passed = False
        self.perfect = False
        self.status = SubmissionStatus.FAILED

        self.game_mode = 0
        self.play_time = 0

        # osu!'s client 'anticheat'.
        self.client_flags = ClientFlags.Clean

    @classmethod
    def from_submission(cls, data_enc: str, iv: str,
                        osu_ver: str, pass_md5: str) -> None:
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

        s = cls()

        s.map_md5 = data[0]
        if len(s.map_md5) != 32:
            return

        s.map_id = res['id'] if (res := glob.db.fetch(
            'SELECT id FROM maps WHERE md5 = %s', [s.map_md5])
        ) else 0

        # why does osu! make me rstrip lol
        s.player = glob.players.get_from_cred(data[1].rstrip(), pass_md5)
        if not s.player:
            # Return the obj with an empty player to
            # determine whether the score faield to
            # be parsed vs. the user could not be found
            # logged in (we want to not send a reply to
            # the osu! client if they're simply not logged
            # in, so that it will retry once they login).
            return s

        # XXX: unused idx 2: online score checksum
        # Perhaps will use to improve security at some point?

        # Ensure all ints are safe to cast.
        if not all(i.isnumeric() for i in data[3:11] + [data[13] + data[15]]):
            print('Invalid parameter passed into submit-modular.')
            return

        s.n300, s.n100, s.n50, s.ngeki, s.nkatu, s.nmiss, \
        s.score, s.max_combo = (int(i) for i in data[3:11])

        s.perfect = data[11] == '1'
        s.grade = data[12] # letter grade
        s.mods = int(data[13])
        s.passed = data[14] == 'True'
        s.game_mode = int(data[15])
        s.play_time = int(time()) # (yyMMddHHmmss)
        s.client_flags = data[17].count(' ') # TODO: use osu!ver? (osuver\s+)

        # All data read from submission.
        # Now we can calculate things based on our data.
        s.calc_accuracy()
        s.pp = s.calc_diff()[0] if s.map_id else 0.0 # Ignore SR for now.
        s.calc_status()
        s.rank = s.calc_lb_placement()

        return s

    def calc_lb_placement(self) -> int:
        if self.mods & Mods.RELAX:
            table = 'scores_rx'
            scoring = 'pp'
            score = self.score
        else:
            table = 'scores_vn'
            scoring = 'score'
            score = self.pp

        res = glob.db.fetch(
            'SELECT COUNT(*) AS c FROM {t} '
            'WHERE map_md5 = %s AND game_mode = %s '
            'AND status = 2 AND {s} > %s'.format(t = table, s = scoring), [
                self.map_md5, self.game_mode, score
            ]
        )

        return res['c'] + 1 if res else 1

    # Could be staticmethod?
    # We'll see after some usage of gulag
    # whether it's beneficial or not.
    def calc_diff(self) -> Tuple[float, float]:
        """Calculate PP and star rating for our score."""
        if self.game_mode not in {0, 1}:
            # Currently only std and taiko are supported,
            # since we are simply using oppai-ng alone.
            return (0.0, 0.0)

        owpi: Owoppai = Owoppai(
            map_id = self.map_id,
            mods = self.mods,
            combo = self.max_combo,
            misses = self.nmiss,
            gamemode = self.game_mode,
            accuracy = self.acc
        )

        # Returns (pp, sr)
        return owpi.calculate_pp()

    def calc_status(self) -> None:
        if not self.passed:
            self.status = SubmissionStatus.FAILED
            return

        table = 'scores_rx' if self.mods & Mods.RELAX else 'scores_vn'

        # try to find a better pp score than this one.
        # if this exists, it will be s=1
        res = glob.db.fetch(
            f'SELECT 1 FROM {table} WHERE userid = %s '
            'AND map_md5 = %s AND game_mode = %s '
            'AND pp > %s AND status = 2', [
                self.player.id, self.map_md5,
                self.game_mode, self.pp
            ]
        )

        self.status = SubmissionStatus.SUBMITTED if res \
                 else SubmissionStatus.BEST

    def calc_accuracy(self) -> None:
        if self.game_mode == 0: # osu!
            if not (total := sum((self.n300, self.n100, self.n50, self.nmiss))):
                self.acc = 0.0
                return

            self.acc = 100.0 * sum((
                self.n50 * 50.0,
                self.n100 * 100.0,
                self.n300 * 300.0
            )) / (total * 300.0)

        elif self.game_mode == 1: # osu!taiko
            if not (total := sum((self.n300, self.n100, self.nmiss))):
                self.acc = 0.0
                return

            self.acc = 100.0 * sum((
                self.n100 * 150.0,
                self.n300 * 300.0
            )) / (total * 300.0)

        elif self.game_mode == 2:
            # osu!catch
            pass
        elif self.game_mode == 3:
            # osu!mania
            pass
