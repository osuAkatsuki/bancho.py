import functools
import math
from datetime import datetime
from enum import IntEnum
from enum import unique
from pathlib import Path
from typing import Optional
from typing import TYPE_CHECKING

from cmyui.osu.oppai_ng import OppaiWrapper
from peace_performance_python.objects import Beatmap as PeaceMap
from peace_performance_python.objects import Calculator as PeaceCalculator

from app.constants.clientflags import ClientFlags
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.objects.beatmap import Beatmap
from app.utils import escape_enum
from app.utils import pymysql_encode

if TYPE_CHECKING:
    from app.objects.player import Player

__all__ = ("Grade", "SubmissionStatus", "Score")

BEATMAPS_PATH = Path.cwd() / ".data/osu"


@unique
class Grade(IntEnum):
    # NOTE: these are implemented in the opposite order
    # as osu! to make more sense with <> operators.
    N = 0
    F = 1
    D = 2
    C = 3
    B = 4
    A = 5
    S = 6  # S
    SH = 7  # HD S
    X = 8  # SS
    XH = 9  # HD SS

    @classmethod
    @functools.cache
    def from_str(cls, s: str) -> "Grade":
        return {
            "xh": Grade.XH,
            "x": Grade.X,
            "sh": Grade.SH,
            "s": Grade.S,
            "a": Grade.A,
            "b": Grade.B,
            "c": Grade.C,
            "d": Grade.D,
            "f": Grade.F,
            "n": Grade.N,
        }[s.lower()]

    def __format__(self, format_spec: str) -> str:
        if format_spec == "stats_column":
            return f"{self.name.lower()}_count"
        else:
            raise ValueError(f"Invalid format specifier {format_spec}")


@unique
@pymysql_encode(escape_enum)
class SubmissionStatus(IntEnum):
    # TODO: make a system more like bancho's?
    FAILED = 0
    SUBMITTED = 1
    BEST = 2

    def __repr__(self) -> str:
        return {self.FAILED: "Failed", self.SUBMITTED: "Submitted", self.BEST: "Best"}[
            self
        ]


class Score:
    """\
    Server side representation of an osu! score; any gamemode.

    Possibly confusing attributes
    -----------
    bmap: Optional[`Beatmap`]
        A beatmap obj representing the osu map.

    player: Optional[`Player`]
        A player obj of the player who submitted the score.

    grade: `Grade`
        The letter grade in the score.

    rank: `int`
        The leaderboard placement of the score.

    perfect: `bool`
        Whether the score is a full-combo.

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
        "id",
        "bmap",
        "player",
        "mode",
        "mods",
        "pp",
        "sr",
        "score",
        "max_combo",
        "acc",
        "n300",
        "n100",
        "n50",
        "nmiss",
        "ngeki",
        "nkatu",
        "grade",
        "rank",
        "passed",
        "perfect",
        "status",
        "play_time",
        "time_elapsed",
        "client_flags",
        "online_checksum",
        "prev_best",
    )

    def __init__(self):
        # TODO: check whether the reamining Optional's should be
        self.id: Optional[int] = None
        self.bmap: Optional[Beatmap] = None
        self.player: Optional["Player"] = None

        self.mode: GameMode
        self.mods: Mods

        self.pp: float
        self.sr: float
        self.score: int
        self.max_combo: int
        self.acc: float

        # TODO: perhaps abstract these differently
        # since they're mode dependant? feels weird..
        self.n300: int
        self.n100: int  # n150 for taiko
        self.n50: int
        self.nmiss: int
        self.ngeki: int
        self.nkatu: int

        self.grade: Grade

        self.passed: bool
        self.perfect: bool
        self.status: SubmissionStatus

        self.play_time: datetime
        self.time_elapsed: int

        self.client_flags: ClientFlags
        self.online_checksum: str

        self.rank: Optional[int] = None
        self.prev_best: Optional[Score] = None

    def __repr__(self) -> str:  # maybe shouldn't be so long?
        return (
            f"<{self.acc:.2f}% {self.max_combo}x {self.nmiss}M "
            f"#{self.rank} on {self.bmap.full} for {self.pp:,.2f}pp>"
        )

    """Classmethods to fetch a score object from various data types."""

    @classmethod
    async def from_sql(cls, score_id: int, scores_table: str) -> Optional["Score"]:
        """Create a score object from sql using it's scoreid."""
        # XXX: perhaps in the future this should take a gamemode rather
        # than just the sql table? just faster on the current setup :P
        res = await app.state.services.database.fetch(
            "SELECT id, map_md5, userid, pp, score, "
            "max_combo, mods, acc, n300, n100, n50, "
            "nmiss, ngeki, nkatu, grade, perfect, "
            "status, mode, play_time, "
            "time_elapsed, client_flags, online_checksum "
            f"FROM {scores_table} WHERE id = %s",
            [score_id],
            _dict=False,
        )

        if not res:
            return

        s = cls()

        s.id = res[0]
        s.bmap = await Beatmap.from_md5(res[1])
        s.player = await app.state.sessions.players.from_cache_or_sql(id=res[2])

        s.sr = 0.0  # TODO

        (
            s.pp,
            s.score,
            s.max_combo,
            s.mods,
            s.acc,
            s.n300,
            s.n100,
            s.n50,
            s.nmiss,
            s.ngeki,
            s.nkatu,
            s.grade,
            s.perfect,
            s.status,
            mode_vn,
            s.play_time,
            s.time_elapsed,
            s.client_flags,
            s.online_checksum,
        ) = res[3:]

        # fix some types
        s.passed = s.status != 0
        s.status = SubmissionStatus(s.status)
        s.grade = Grade.from_str(s.grade)
        s.mods = Mods(s.mods)
        s.mode = GameMode.from_params(mode_vn, s.mods)
        s.client_flags = ClientFlags(s.client_flags)

        if s.bmap:
            s.rank = await s.calc_lb_placement()

        return s

    @classmethod
    async def from_submission(cls, data: list[str]) -> "Score":
        """Create a score object from an osu! submission string."""
        s = cls()

        """ parse the following format
        # 0  online_checksum
        # 1  n300
        # 2  n100
        # 3  n50
        # 4  ngeki
        # 5  nkatu
        # 6  nmiss
        # 7  score
        # 8  max_combo
        # 9  perfect
        # 10 grade
        # 11 mods
        # 12 passed
        # 13 gamemode
        # 14 play_time # yyMMddHHmmss
        # 15 osu_version + (" " * client_flags)
        """

        s.online_checksum = data[0]

        s.n300, s.n100, s.n50, s.ngeki, s.nkatu, s.nmiss, s.score, s.max_combo = map(
            int,
            data[1:9],
        )

        s.perfect = data[9] == "True"
        _grade = data[10]  # letter grade
        s.mods = Mods(int(data[11]))
        s.passed = data[12] == "True"
        s.mode = GameMode.from_params(int(data[13]), s.mods)

        # TODO: we might want to use data[14] to get more
        #       accurate submission time (client side) but
        #       we'd probably want to check if it's close.
        s.play_time = datetime.now()

        s.client_flags = ClientFlags(data[15].count(" ") & ~4)

        s.grade = Grade.from_str(_grade) if s.passed else Grade.F

        return s

    """Methods to calculate internal data for a score."""

    async def calc_lb_placement(self) -> int:
        scores_table = self.mode.scores_table

        if self.mode >= GameMode.RELAX_OSU:
            scoring_metric = "pp"
            score = self.pp
        else:
            scoring_metric = "score"
            score = self.score

        res = await app.state.services.database.fetch(
            f"SELECT COUNT(*) AS c FROM {scores_table} s "
            "INNER JOIN users u ON u.id = s.userid "
            "WHERE s.map_md5 = %s AND s.mode = %s "
            "AND s.status = 2 AND u.priv & 1 "
            f"AND s.{scoring_metric} > %s",
            [self.bmap.md5, self.mode.as_vanilla, score],
        )

        return res["c"] + 1 if res else 1

    def calc_diff(self, osu_file_path: Path) -> tuple[float, float]:
        """Calculate PP and star rating for our score."""
        mode_vn = self.mode.as_vanilla

        if mode_vn == 0:  # std
            with OppaiWrapper("oppai-ng/liboppai.so") as ezpp:
                if self.mods:
                    ezpp.set_mods(int(self.mods))

                if mode_vn:
                    ezpp.set_mode(mode_vn)

                ezpp.set_combo(self.max_combo)
                ezpp.set_nmiss(self.nmiss)  # clobbers acc
                ezpp.set_accuracy_percent(self.acc)

                ezpp.calculate(osu_file_path)

                pp = ezpp.get_pp()

                if math.isnan(pp) or math.isinf(pp):
                    # TODO: report to logserver
                    return (0.0, 0.0)

                return (round(pp, 5), ezpp.get_sr())
        elif mode_vn in (1, 2):  # taiko, catch
            beatmap = PeaceMap(osu_file_path)
            peace = PeaceCalculator()

            if self.mods != Mods.NOMOD:
                peace.set_mods(int(self.mods))

            if mode_vn:
                peace.set_mode(mode_vn)

            peace.set_combo(self.max_combo)
            peace.set_miss(self.nmiss)
            peace.set_acc(self.acc)

            calculated = peace.calculate(beatmap)

            if math.isnan(calculated.pp) or math.isinf(calculated.pp):
                # TODO: report to logserver
                return (0.0, 0.0)

            return (round(calculated.pp, 5), calculated.stars)
        elif mode_vn == 3:  # mania
            beatmap = PeaceMap(osu_file_path)
            peace = PeaceCalculator()

            if self.mods != Mods.NOMOD:
                peace.set_mods(int(self.mods))

            if mode_vn:
                peace.set_mode(mode_vn)

            peace.set_score(self.score)
            calculated = peace.calculate(beatmap)

            if math.isnan(calculated.pp) or math.isinf(calculated.pp):
                # TODO: report to logserver
                return (0.0, 0.0)

            return (round(calculated.pp, 5), calculated.stars)
        else:
            raise ValueError(f"Invalid vanilla mode {mode_vn}")

    async def calc_status(self) -> None:
        """Calculate the submission status of a submitted score."""
        scores_table = self.mode.scores_table

        # find any other `status = 2` scores we have
        # on the map. If there are any, store
        res = await app.state.services.database.fetch(
            f"SELECT id, pp FROM {scores_table} "
            "WHERE userid = %s AND map_md5 = %s "
            "AND mode = %s AND status = 2",
            [self.player.id, self.bmap.md5, self.mode.as_vanilla],
        )

        if res:
            # we have a score on the map.
            # save it as our previous best score.
            self.prev_best = await Score.from_sql(res["id"], scores_table)

            # if our new score is better, update
            # both of our score's submission statuses.
            # NOTE: this will be updated in sql later on in submission
            if self.pp > res["pp"]:
                self.status = SubmissionStatus.BEST
                self.prev_best.status = SubmissionStatus.SUBMITTED
            else:
                self.status = SubmissionStatus.SUBMITTED
        else:
            # this is our first score on the map.
            self.status = SubmissionStatus.BEST

    def calc_accuracy(self) -> float:
        """Calculate the accuracy of our score."""
        mode_vn = self.mode.as_vanilla

        if mode_vn == 0:  # osu!
            total = self.n300 + self.n100 + self.n50 + self.nmiss

            if total == 0:
                return 0.0

            return (
                100.0
                * ((self.n300 * 300.0) + (self.n100 * 100.0) + (self.n50 * 50.0))
                / (total * 300.0)
            )

        elif mode_vn == 1:  # osu!taiko
            total = self.n300 + self.n100 + self.nmiss

            if total == 0:
                return 0.0

            return 100.0 * ((self.n100 * 0.5) + self.n300) / total

        elif mode_vn == 2:  # osu!catch
            total = self.n300 + self.n100 + self.n50 + self.nkatu + self.nmiss

            if total == 0:
                return 0.0

            return 100.0 * (self.n300 + self.n100 + self.n50) / total

        elif mode_vn == 3:  # osu!mania
            total = (
                self.n300 + self.n100 + self.n50 + self.ngeki + self.nkatu + self.nmiss
            )

            if total == 0:
                return 0.0

            return (
                100.0
                * (
                    (self.n50 * 50.0)
                    + (self.n100 * 100.0)
                    + (self.nkatu * 200.0)
                    + ((self.n300 + self.ngeki) * 300.0)
                )
                / (total * 300.0)
            )
        else:
            raise Exception(f"Invalid vanilla mode {mode_vn}")
