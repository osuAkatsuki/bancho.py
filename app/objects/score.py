from __future__ import annotations

import functools
import hashlib
from datetime import datetime
from enum import IntEnum
from enum import unique
from pathlib import Path
from typing import Optional

from app.constants.clientflags import ClientFlags
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.utils import escape_enum
from app.utils import pymysql_encode

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

    __slots__ = (
        "id",
        "bmap_md5",
        "player_name",
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
        "client_time",
        "server_time",
        "time_elapsed",
        "client_flags",
        "client_checksum",
        "prev_best",
    )

    def __init__(self):
        self.id: int
        self.bmap_md5: str
        self.player_name: str

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
                f"#{self.rank} on {self.bmap_md5} for {self.pp:,.2f}pp>"
            )
        except:
            return super().__repr__()

    """Classmethods to fetch a score object from various data types."""

    @classmethod
    def from_row(cls, row) -> Score:  # TODO: row type
        score = cls()

        (
            score.id,
            score.bmap_md5,
            score.player_name,
            score.pp,
            score.score,
            score.max_combo,
            score.mods,
            score.acc,
            score.n300,
            score.n100,
            score.n50,
            score.nmiss,
            score.ngeki,
            score.nkatu,
            score.grade,
            score.perfect,
            score.status,
            score.mode,
            score.server_time,
            score.time_elapsed,
            score.client_flags,
            score.client_checksum,
        ) = row

        # fix some types
        score.passed = score.status != 0
        score.status = SubmissionStatus(score.status)
        score.grade = Grade.from_str(score.grade)
        score.mods = Mods(score.mods)
        score.mode = GameMode(score.mode)
        score.client_flags = ClientFlags(score.client_flags)

        score.sr = 0.0  # TODO

        # TODO: ensure this is everywhere required
        # if score.bmap:
        #    score.rank = await score.calculate_placement()

        return score

    @classmethod
    def from_submission(cls, data: list[str]) -> Score:
        """Create a score object from an osu! submission string."""
        score = cls()

        """ parse the following format
        # 0  beatmap_md5
        # 1
        # 1  online_checksum
        # 2  n300
        # 3  n100
        # 4  n50
        # 5  ngeki
        # 6  nkatu
        # 7  nmiss
        # 8  score
        # 9  max_combo
        # 10  perfect
        # 11 grade
        # 12 mods
        # 13 passed
        # 14 gamemode
        # 15 play_time # yyMMddHHmmss
        # 16 osu_version + (" " * client_flags)
        """

        score.bmap_md5 = data[0]
        score.player_name = data[1].rstrip()  # ends with ' ' if client has supporter
        score.client_checksum = data[2]
        score.n300 = int(data[3])
        score.n100 = int(data[4])
        score.n50 = int(data[5])
        score.ngeki = int(data[6])
        score.nkatu = int(data[7])
        score.nmiss = int(data[8])
        score.score = int(data[9])
        score.max_combo = int(data[10])
        score.perfect = data[11] == "True"
        score.grade = Grade.from_str(data[12])
        score.mods = Mods(int(data[13]))
        score.passed = data[14] == "True"
        score.mode = GameMode.from_params(int(data[15]), score.mods)
        score.client_time = datetime.strptime(data[16], "%y%m%d%H%M%S")
        score.client_flags = ClientFlags(data[17].count(" ") & ~4)

        score.server_time = datetime.now()

        return score

    def compute_online_checksum(
        self,
        osu_version: str,
        osu_client_hash: str,
        storyboard_checksum: str,
    ) -> str:
        """Validate the online checksum of the score."""
        return hashlib.md5(
            "chickenmcnuggets{0}o15{1}{2}smustard{3}{4}uu{5}{6}{7}{8}{9}{10}{11}Q{12}{13}{15}{14:%y%m%d%H%M%S}{16}{17}".format(
                self.n100 + self.n300,
                self.n50,
                self.ngeki,
                self.nkatu,
                self.nmiss,
                self.bmap_md5,
                self.max_combo,
                self.perfect,
                self.player_name,
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
