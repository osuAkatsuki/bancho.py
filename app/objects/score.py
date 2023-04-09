from __future__ import annotations

import functools
import hashlib
from datetime import datetime
from enum import IntEnum
from enum import unique
from pathlib import Path
from typing import Optional
from typing import TYPE_CHECKING

import app.state
import app.usecases.performance
import app.utils
from app.constants.clientflags import ClientFlags
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.objects.beatmap import Beatmap
from app.repositories import scores as scores_repo
from app.usecases.performance import ScoreParams
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
    def from_str(cls, s: str) -> Grade:
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
        return {
            self.FAILED: "Failed",
            self.SUBMITTED: "Submitted",
            self.BEST: "Best",
        }[self]


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

    def __init__(self) -> None:
        # TODO: check whether the reamining Optional's should be
        self.id: Optional[int] = None
        self.bmap: Optional[Beatmap] = None
        self.player: Optional[Player] = None

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

        self.client_time: datetime
        self.server_time: datetime
        self.time_elapsed: int

        self.client_flags: ClientFlags
        self.client_checksum: str

        self.rank: Optional[int] = None
        self.prev_best: Optional[Score] = None

    def __repr__(self) -> str:
        # TODO: i really need to clean up my reprs
        try:
            return (
                f"<{self.acc:.2f}% {self.max_combo}x {self.nmiss}M "
                f"#{self.rank} on {self.bmap.full_name} for {self.pp:,.2f}pp>"
            )
        except:
            return super().__repr__()

    """Classmethods to fetch a score object from various data types."""

    @classmethod
    async def from_sql(cls, score_id: int) -> Optional[Score]:
        """Create a score object from sql using its scoreid."""
        rec = await scores_repo.fetch_one(score_id)

        if rec is None:
            return None

        s = cls()

        s.id = rec["id"]
        s.bmap = await Beatmap.from_md5(rec["map_md5"])
        s.player = await app.state.sessions.players.from_cache_or_sql(id=rec["userid"])

        s.sr = 0.0  # TODO

        s.pp = rec["pp"]
        s.score = rec["score"]
        s.max_combo = rec["max_combo"]
        s.mods = rec["mods"]
        s.acc = rec["acc"]
        s.n300 = rec["n300"]
        s.n100 = rec["n100"]
        s.n50 = rec["n50"]
        s.nmiss = rec["nmiss"]
        s.ngeki = rec["ngeki"]
        s.nkatu = rec["nkatu"]
        s.grade = rec["grade"]
        s.perfect = rec["perfect"]
        s.status = rec["status"]
        s.mode = rec["mode"]
        s.server_time = rec["play_time"]
        s.time_elapsed = rec["time_elapsed"]
        s.client_flags = rec["client_flags"]
        s.client_checksum = rec["online_checksum"]

        # fix some types
        s.passed = s.status != 0
        s.status = SubmissionStatus(s.status)
        s.grade = Grade.from_str(s.grade)
        s.mods = Mods(s.mods)
        s.mode = GameMode(s.mode)
        s.client_flags = ClientFlags(s.client_flags)

        if s.bmap:
            s.rank = await s.calculate_placement()

        return s

    @classmethod
    def from_submission(cls, data: list[str]) -> Score:
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

        s.client_checksum = data[0]
        s.n300 = int(data[1])
        s.n100 = int(data[2])
        s.n50 = int(data[3])
        s.ngeki = int(data[4])
        s.nkatu = int(data[5])
        s.nmiss = int(data[6])
        s.score = int(data[7])
        s.max_combo = int(data[8])
        s.perfect = data[9] == "True"
        s.grade = Grade.from_str(data[10])
        s.mods = Mods(int(data[11]))
        s.passed = data[12] == "True"
        s.mode = GameMode.from_params(int(data[13]), s.mods)
        s.client_time = datetime.strptime(data[14], "%y%m%d%H%M%S")
        s.client_flags = ClientFlags(data[15].count(" ") & ~4)

        s.server_time = datetime.now()

        return s

    def compute_online_checksum(
        self,
        osu_version: str,
        osu_client_hash: str,
        storyboard_checksum: str,
    ) -> str:
        """Validate the online checksum of the score."""
        assert self.player is not None
        assert self.bmap is not None

        return hashlib.md5(
            "chickenmcnuggets{0}o15{1}{2}smustard{3}{4}uu{5}{6}{7}{8}{9}{10}{11}Q{12}{13}{15}{14:%y%m%d%H%M%S}{16}{17}".format(
                self.n100 + self.n300,
                self.n50,
                self.ngeki,
                self.nkatu,
                self.nmiss,
                self.bmap.md5,
                self.max_combo,
                self.perfect,
                self.player.name,
                self.score,
                self.grade.name,
                int(self.mods),
                self.passed,
                self.mode.as_vanilla,
                self.client_time,
                osu_version,  # 20210520
                osu_client_hash,
                storyboard_checksum,
                # yyMMddHHmmss
            ).encode(),
        ).hexdigest()

    """Methods to calculate internal data for a score."""

    async def calculate_placement(self) -> int:
        assert self.bmap is not None

        if self.mode >= GameMode.RELAX_OSU:
            scoring_metric = "pp"
            score = self.pp
        else:
            scoring_metric = "score"
            score = self.score

        better_scores = await app.state.services.database.fetch_val(
            "SELECT COUNT(*) AS c FROM scores s "
            "INNER JOIN users u ON u.id = s.userid "
            "WHERE s.map_md5 = :map_md5 AND s.mode = :mode "
            "AND s.status = 2 AND u.priv & 1 "
            f"AND s.{scoring_metric} > :score",
            {
                "map_md5": self.bmap.md5,
                "mode": self.mode,
                "score": score,
            },
            column=0,  # COUNT(*)
        )

        # TODO: idk if returns none
        return better_scores + 1  # if better_scores is not None else 1

    def calculate_performance(self, osu_file_path: Path) -> tuple[float, float]:
        """Calculate PP and star rating for our score."""
        mode_vn = self.mode.as_vanilla

        score_args = ScoreParams(
            mode=mode_vn,
            mods=int(self.mods),
            combo=self.max_combo,
            # prefer to use the score's specific params that add up to the acc
            acc=self.acc,
            ngeki=self.ngeki,
            n300=self.n300,
            nkatu=self.nkatu,
            n100=self.n100,
            n50=self.n50,
            nmiss=self.nmiss,
        )

        result = app.usecases.performance.calculate_performances(
            osu_file_path=str(osu_file_path),
            scores=[score_args],
        )

        return result[0]["performance"], result[0]["star_rating"]

    async def calculate_status(self) -> None:
        """Calculate the submission status of a submitted score."""
        assert self.player is not None
        assert self.bmap is not None

        recs = await scores_repo.fetch_many(
            user_id=self.player.id,
            map_md5=self.bmap.md5,
            mode=self.mode,
            status=SubmissionStatus.BEST,
        )

        if recs:
            rec = recs[0]

            # we have a score on the map.
            # save it as our previous best score.
            self.prev_best = await Score.from_sql(rec["id"])
            assert self.prev_best is not None

            # if our new score is better, update
            # both of our score's submission statuses.
            # NOTE: this will be updated in sql later on in submission
            if self.pp > rec["pp"]:
                self.status = SubmissionStatus.BEST
                self.prev_best.status = SubmissionStatus.SUBMITTED
            else:
                self.status = SubmissionStatus.SUBMITTED
        else:
            # this is our first score on the map.
            self.status = SubmissionStatus.BEST

    def calculate_accuracy(self) -> float:
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

            if self.mods & Mods.SCOREV2:
                return (
                    100.0
                    * (
                        (self.n50 * 50.0)
                        + (self.n100 * 100.0)
                        + (self.nkatu * 200.0)
                        + (self.n300 * 300.0)
                        + (self.ngeki * 305.0)
                    )
                    / (total * 305.0)
                )

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

    """ Methods for updating a score. """

    async def increment_replay_views(self) -> None:
        # TODO: move replay views to be per-score rather than per-user
        assert self.player is not None

        # TODO: apparently cached stats don't store replay views?
        #       need to refactor that to be able to use stats_repo here
        await app.state.services.database.execute(
            f"UPDATE stats "
            "SET replay_views = replay_views + 1 "
            "WHERE id = :user_id AND mode = :mode",
            {"user_id": self.player.id, "mode": self.mode},
        )
