# -*- coding: utf-8 -*-

from base64 import b64decode
from datetime import datetime
from enum import IntEnum
from enum import unique
from typing import Optional
from typing import TYPE_CHECKING

from cmyui import Ansi
from cmyui import log
from py3rijndael import RijndaelCbc
from py3rijndael import ZeroPadding

from constants.clientflags import ClientFlags
from constants.gamemodes import GameMode
from constants.mods import Mods
from objects import glob
from objects.beatmap import Beatmap
from utils.recalculator import PPCalculator
from utils.misc import escape_enum
from utils.misc import pymysql_encode

if TYPE_CHECKING:
    from objects.player import Player

__all__ = (
    'Grade',
    'SubmissionStatus',
    'Score'
)

@unique
@pymysql_encode(escape_enum)
class Grade(IntEnum):
    XH = 0 # HD SS
    X  = 1 # SS
    SH = 2 # HD S
    S  = 3 # S
    A  = 4
    B  = 5
    C  = 6
    D  = 7
    F  = 8
    N  = 9

    def __str__(self) -> str:
        return {
            self.XH: 'SS',
            self.X: 'SS',
            self.SH: 'S',
            self.S: 'S',
            self.A: 'A',
            self.B: 'B',
            self.C: 'C',
            self.D: 'D',
            self.F: 'F'
        }[self.value]

    @classmethod
    def from_str(cls, s: str, hidden: bool = False) -> 'Grade':
        return {
            'SS': cls.XH if hidden else cls.SH,
            'S': cls.SH if hidden else cls.S,
            'A': cls.A,
            'B': cls.B,
            'C': cls.C,
            'D': cls.D,
            'F': cls.F,
            'N': cls.N
        }[s]

@unique
@pymysql_encode(escape_enum)
class SubmissionStatus(IntEnum):
    # TODO: make a system more like bancho's?
    FAILED = 0
    SUBMITTED = 1
    BEST = 2

    def __repr__(self) -> str:
        return {
            self.FAILED: 'Failed',
            self.SUBMITTED: 'Submitted',
            self.BEST: 'Best'
        }[self.value]

class Score:
    """\
    Server side representation of an osu! score; any gamemode.

    Attributes
    -----------
    id: `int`
        The score's unique ID.

    bmap: Optional[`Beatmap`]
        A beatmap obj representing the osu map.

    player: Optional[`Player`]
        A player obj of the player who submitted the score.

    pp: `float`
        The score's performance points.

    score: `int`
        The score's osu! score value.

    max_combo: `int`
        The maximum combo reached in the score.

    mods: `Mods`
        A bitwise value of the osu! mods used in the score.

    acc: `float`
        The accuracy of the score.

    n300: `int`
        The number of 300s in the score.

    n100: `int`
        The number of 100s in the score (150s if taiko).

    n50: `int`
        The number of 50s in the score.

    nmiss: `int`
        The number of misses in the score.

    ngeki: `int`
        The number of gekis in the score.

    nkatu: `int`
        The number of katus in the score.

    grade: `Grade`
        The letter grade in the score.

    rank: `int`
        The leaderboard placement of the score.

    passed: `bool`
        Whether the score completed the map.

    perfect: `bool`
        Whether the score is a full-combo.

    status: `SubmissionStatus`
        The submission status of the score.

    mode: `GameMode`
        The game mode of the score.

    play_time: `datetime`
        A datetime obj of the time of score submission.

    time_elapsed: `int`
        The total elapsed time of the play (in milliseconds).

    client_flags: `int`
        osu!'s old anticheat flags.

    prev_best: Optional[`Score`]
        The previous best score before this play was submitted.
        NOTE: just because a score has a `prev_best` attribute does
        mean the score is our best score on the map! the `status`
        value will always be accurate for any score.
    """
    __slots__ = (
        'id', 'bmap', 'player',
        'pp', 'sr', 'score', 'max_combo', 'mods',
        'acc', 'n300', 'n100', 'n50', 'nmiss', 'ngeki', 'nkatu', 'grade',
        'rank', 'passed', 'perfect', 'status',
        'mode', 'play_time', 'time_elapsed',
        'client_flags', 'prev_best'
    )

    def __init__(self):
        self.id: Optional[int] = None

        self.bmap: Optional[Beatmap] = None
        self.player: Optional['Player'] = None

        # pp & star rating
        self.pp: Optional[float] = None
        self.sr: Optional[float] = None

        self.score: Optional[int] = None
        self.max_combo: Optional[int] = None
        self.mods: Optional[Mods] = None

        self.acc: Optional[float] = None
        # TODO: perhaps abstract these differently
        # since they're mode dependant? feels weird..
        self.n300: Optional[int] = None
        self.n100: Optional[int] = None # n150 for taiko
        self.n50: Optional[int] = None
        self.nmiss: Optional[int] = None
        self.ngeki: Optional[int] = None
        self.nkatu: Optional[int] = None
        self.grade: Optional[Grade] = None

        self.rank: Optional[int] = None
        self.passed: Optional[bool] = None
        self.perfect: Optional[bool] = None
        self.status: Optional[SubmissionStatus] = None

        self.mode: Optional[GameMode] = None
        self.play_time: Optional[datetime] = None
        self.time_elapsed: Optional[datetime] = None

        # osu!'s client 'anticheat'.
        self.client_flags: Optional[ClientFlags] = None

        self.prev_best: Optional[Score] = None

    @classmethod
    async def from_sql(cls, scoreid: int, sql_table: str):
        """Create a score object from sql using it's scoreid."""
        # XXX: perhaps in the future this should take a gamemode rather
        # than just the sql table? just faster on the current setup :P
        res = await glob.db.fetch(
            'SELECT id, map_md5, userid, pp, score, '
            'max_combo, mods, acc, n300, n100, n50, '
            'nmiss, ngeki, nkatu, grade, perfect, '
            'status, mode, play_time, '
            'time_elapsed, client_flags '
            f'FROM {sql_table} WHERE id = %s',
            [scoreid], _dict=False
        )

        if not res:
            return

        s = cls()

        s.id = res[0]
        s.bmap = await Beatmap.from_md5(res[1])
        s.player = await glob.players.get_ensure(id=res[2])

        (s.pp, s.score, s.max_combo, s.mods, s.acc, s.n300,
         s.n100, s.n50, s.nmiss, s.ngeki, s.nkatu, s.grade,
         s.perfect, s.status, mode_vn, s.play_time,
         s.time_elapsed, s.client_flags) = res[3:]

        # fix some types
        s.passed = s.status != 0
        s.status = SubmissionStatus(s.status)
        s.mods = Mods(s.mods)
        s.mode = GameMode.from_params(mode_vn, s.mods)
        s.client_flags = ClientFlags(s.client_flags)

        if s.bmap:
            s.rank = await s.calc_lb_placement()

        return s

    @classmethod
    async def from_submission(cls, data_b64: str, iv_b64: str,
                              osu_ver: str, pw_md5: str) -> Optional['Score']:
        """Create a score object from an osu! submission string."""
        iv = b64decode(iv_b64).decode('latin_1')
        data_aes = b64decode(data_b64).decode('latin_1')

        aes_key = f'osu!-scoreburgr---------{osu_ver}'
        aes = RijndaelCbc(aes_key, iv, ZeroPadding(32), 32)

        # score data is delimited by colons (:).
        data = aes.decrypt(data_aes).decode().split(':')

        if len(data) != 18:
            log('Received an invalid score submission.', Ansi.LRED)
            return

        s = cls()

        if len(map_md5 := data[0]) != 32:
            return

        pname = data[1].rstrip() # why does osu! make me rstrip lol

        # get the map & player for the score.
        s.bmap = await Beatmap.from_md5(map_md5)
        s.player = await glob.players.get_login(pname, pw_md5)

        if not s.player:
            # return the obj with an empty player to
            # determine whether the score faield to
            # be parsed vs. the user could not be found
            # logged in (we want to not send a reply to
            # the osu! client if they're simply not logged
            # in, so that it will retry once they login).
            return s

        # XXX: unused idx 2: online score checksum
        # perhaps will use to improve security at some point?

        # ensure all ints are safe to cast.
        if not all(map(str.isdecimal, data[3:11] + [data[13], data[15]])):
            log('Invalid parameter passed into submit-modular.', Ansi.LRED)
            return

        (s.n300, s.n100, s.n50, s.ngeki, s.nkatu, s.nmiss,
         s.score, s.max_combo) = map(int, data[3:11])

        s.perfect = data[11] == 'True'
        _grade = data[12] # letter grade
        s.mods = Mods(int(data[13]))
        s.passed = data[14] == 'True'
        s.mode = GameMode.from_params(int(data[15]), s.mods)
        s.play_time = datetime.now()
        s.client_flags = data[17].count(' ') # TODO: use osu!ver? (osuver\s+)

        s.grade = _grade if s.passed else 'F'

        # all data read from submission.
        # now we can calculate things based on our data.
        s.calc_accuracy()

        if s.bmap:
            # ignore sr for now.
            s.pp, s.sr = await s.calc_diff()

            await s.calc_status()
            s.rank = await s.calc_lb_placement()
        else:
            s.pp = s.sr = 0.0
            if s.passed:
                s.status = SubmissionStatus.SUBMITTED
            else:
                s.status = SubmissionStatus.FAILED

        return s

    async def calc_lb_placement(self) -> int:
        table = self.mode.sql_table

        if self.mode >= GameMode.rx_std:
            scoring = 'pp'
            score = self.pp
        else:
            scoring = 'score'
            score = self.score

        res = await glob.db.fetch(
            f'SELECT COUNT(*) AS c FROM {table} s '
            'INNER JOIN users u ON u.id = s.userid '
            'WHERE s.map_md5 = %s AND s.mode = %s '
            'AND s.status = 2 AND u.priv & 1 '
            f'AND s.{scoring} > %s',
            [self.bmap.md5, self.mode.as_vanilla, score]
        )

        return res['c'] + 1 if res else 1

    # could be staticmethod?
    # we'll see after some usage of gulag
    # whether it's beneficial or not.
    async def calc_diff(self) -> tuple[float, float]:
        """Calculate PP and star rating for our score."""
        mode_vn = self.mode.as_vanilla

        if mode_vn in (0, 1):
            if not glob.oppai_built:
                # oppai-ng not compiled
                return (0.0, 0.0)

            pp_attrs = {
                'mods': self.mods,
                'combo': self.max_combo,
                'nmiss': self.nmiss,
                'mode_vn': mode_vn,
                'acc': self.acc
            }
        elif mode_vn == 2:
            return (0.0, 0.0)
        elif mode_vn == 3:
            if self.bmap.mode.as_vanilla != 3:
                return (0.0, 0.0) # maniera has no convert support

            pp_attrs = {
                'mods': self.mods,
                'score': self.score,
                'mode_vn': mode_vn
            }

        ppcalc = await PPCalculator.from_id(map_id=self.bmap.id, **pp_attrs)

        if not ppcalc:
            return (0.0, 0.0)

        return await ppcalc.perform()

    async def calc_status(self) -> None:
        """Calculate the submission status of a score."""
        if not self.passed:
            self.status = SubmissionStatus.FAILED
            return

        table = self.mode.sql_table

        # find any other `status = 2` scores we have
        # on the map. If there are any, store
        res = await glob.db.fetch(
            f'SELECT id, pp FROM {table} '
            'WHERE userid = %s AND map_md5 = %s '
            'AND mode = %s AND status = 2',
            [self.player.id, self.bmap.md5, self.mode.as_vanilla]
        )

        if res:
            # we have a score on the map.
            # save it as our previous best score.
            self.prev_best = await Score.from_sql(res['id'], table)

            # if our new score is better, update
            # both of our score's submission statuses.
            # NOTE: this will be updated in sql later on in submission
            if self.pp > res['pp']:
                self.status = SubmissionStatus.BEST
                self.prev_best.status = SubmissionStatus.SUBMITTED
            else:
                self.status = SubmissionStatus.SUBMITTED
        else:
            # this is our first score on the map.
            self.status = SubmissionStatus.BEST

    def calc_accuracy(self) -> None:
        """Calculate the accuracy of our score."""
        mode_vn = self.mode.as_vanilla

        if mode_vn == 0: # osu!
            total = sum((self.n300, self.n100, self.n50, self.nmiss))

            if total == 0:
                self.acc = 0.0
                return

            self.acc = 100.0 * sum((
                self.n50 * 50.0,
                self.n100 * 100.0,
                self.n300 * 300.0
            )) / (total * 300.0)

        elif mode_vn == 1: # osu!taiko
            total = sum((self.n300, self.n100, self.nmiss))

            if total == 0:
                self.acc = 0.0
                return

            self.acc = 100.0 * sum((
                self.n100 * 0.5,
                self.n300
            )) / total

        elif mode_vn == 2:
            # osu!catch
            total = sum((self.n300, self.n100, self.n50,
                         self.nkatu, self.nmiss))

            if total == 0:
                self.acc = 0.0
                return

            self.acc = 100.0 * sum((
                self.n300,
                self.n100,
                self.n50
            )) / total

        elif mode_vn == 3:
            # osu!mania
            total = sum((self.n300, self.n100, self.n50,
                         self.ngeki, self.nkatu, self.nmiss))

            if total == 0:
                self.acc = 0.0
                return

            self.acc = 100.0 * sum((
                self.n50 * 50.0,
                self.n100 * 100.0,
                self.nkatu * 200.0,
                (self.n300 + self.ngeki) * 300.0
            )) / (total * 300.0)
