from __future__ import annotations

import functools
import hashlib
from datetime import datetime
from enum import IntEnum
from enum import unique
from pathlib import Path
from typing import Any
from typing import Mapping
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
    UNSUBMITTED = -1
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

    def __init__(
        self,
        id: Optional[int],  # can be None if status == SubmissionStatus.UNSUBMITTED
        bmap_md5: str,
        player_name: str,
        mode: GameMode,
        mods: Mods,
        pp: float,
        sr: float,
        score: int,
        max_combo: int,
        acc: float,
        n300: int,
        n100: int,
        n50: int,
        nmiss: int,
        ngeki: int,
        nkatu: int,
        grade: Grade,
        passed: bool,
        perfect: bool,
        status: SubmissionStatus,
        server_time: datetime,
        time_elapsed: int,
        client_flags: ClientFlags,
        client_checksum: str,
        rank: Optional[int] = None,
        prev_best: Optional[Score] = None,
        # TODO: we should be storing this in the database,
        # and it should be moved back up with server_time
        client_time: Optional[datetime] = None,
    ):
        self.id = id
        self.bmap_md5 = bmap_md5
        self.player_name = player_name
        self.mode = mode
        self.mods = mods
        self.pp = pp
        self.sr = sr
        self.score = score
        self.max_combo = max_combo
        self.acc = acc
        self.n300 = n300
        self.n100 = n100
        self.n50 = n50
        self.nmiss = nmiss
        self.ngeki = ngeki
        self.nkatu = nkatu
        self.grade = grade
        self.passed = passed
        self.perfect = perfect
        self.status = status
        self.client_time = client_time
        self.server_time = server_time
        self.time_elapsed = time_elapsed
        self.client_flags = client_flags
        self.client_checksum = client_checksum
        self.rank = rank
        self.prev_best = prev_best

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
    def from_row(cls, row: Mapping[str, Any]) -> Score:  # TODO: row type
        # TODO: ensure this is everywhere required (after calling Score.from_row)
        # if score.bmap:
        #    score.rank = await score.calculate_placement()

        return cls(
            id=row["id"],
            bmap_md5=row["map_md5"],  # TODO: fix inconsistency
            player_name=row["player_name"],
            pp=row["pp"],
            score=row["score"],
            max_combo=row["max_combo"],
            mods=Mods(row["mods"]),
            acc=row["acc"],
            n300=row["n300"],
            n100=row["n100"],
            n50=row["n50"],
            nmiss=row["nmiss"],
            ngeki=row["ngeki"],
            nkatu=row["nkatu"],
            grade=Grade.from_str(row["grade"]),
            passed=row["status"] != 0,
            perfect=row["perfect"],
            status=SubmissionStatus(row["status"]),
            mode=GameMode(row["mode"]),
            server_time=row["server_time"],
            time_elapsed=row["time_elapsed"],
            client_flags=ClientFlags(row["client_flags"]),
            client_checksum=row["client_checksum"],
            sr=0.0,
        )

    def to_row(self) -> Mapping[str, Any]:
        return {
            "id": self.id,
            "map_md5": self.bmap_md5,  # TODO: fix inconsistency
            "player_name": self.player_name,
            "pp": self.pp,
            "score": self.score,
            "max_combo": self.max_combo,
            "mods": self.mods,
            "acc": self.acc,
            "n300": self.n300,
            "n100": self.n100,
            "n50": self.n50,
            "nmiss": self.nmiss,
            "ngeki": self.ngeki,
            "nkatu": self.nkatu,
            "grade": self.grade.name,
            "perfect": self.perfect,
            "status": self.status,
            "mode": self.mode,
            "server_time": self.server_time,
            "time_elapsed": self.time_elapsed,
            # "client_flags": self.client_flags,
            # "client_checksum": self.client_checksum,
            "passed": self.passed,
            "sr": self.sr,
        }

    @classmethod
    def from_submission(
        cls,
        data: list[str],
        accuracy: float,
        time_elapsed: int,
    ) -> Score:
        """\
        Create a score object from an osu! submission string.

        Parse the following format:
        [0]  beatmap_md5
        [1]  player name
        [2]  online_checksum
        [3]  n300
        [4]  n100
        [5]  n50
        [6]  ngeki
        [7]  nkatu
        [8]  nmiss
        [9]  score
        [10] max_combo
        [11] perfect
        [12] grade
        [13] mods
        [14] passed
        [15] gamemode
        [16] play_time # yyMMddHHmmss
        [17] osu_version + (" " * client_flags)
        """
        return cls(
            id=None,
            bmap_md5=data[0],
            player_name=data[1].rstrip(),  # ends with ' ' if client has supporter
            client_checksum=data[2],
            n300=int(data[3]),
            n100=int(data[4]),
            n50=int(data[5]),
            ngeki=int(data[6]),
            nkatu=int(data[7]),
            nmiss=int(data[8]),
            score=int(data[9]),
            max_combo=int(data[10]),
            perfect=data[11] == "True",
            grade=Grade.from_str(data[12]),
            mods=Mods(int(data[13])),
            passed=data[14] == "True",
            mode=GameMode.from_params(mode_vn=int(data[15]), mods=int(data[13])),
            client_time=datetime.strptime(data[16], "%y%m%d%H%M%S"),
            client_flags=ClientFlags(data[17].count(" ") & ~4),
            acc=accuracy,
            time_elapsed=time_elapsed,
            server_time=datetime.now(),
            # updated upon submission
            status=SubmissionStatus.UNSUBMITTED,
            pp=0.0,
            sr=0.0,
        )

    def compute_online_checksum(
        self,
        osu_version: str,
        osu_client_hash: str,
        storyboard_checksum: str,
    ) -> str:
        """Validate the online checksum of the score."""
        return hashlib.md5(
            (
                "chickenmcnuggets{0}o15{1}{2}smustard{3}{4}uu{5}{6}{7}"
                "{8}{9}{10}{11}Q{12}{13}{15}{14:%y%m%d%H%M%S}{16}{17}"
            )
            .format(
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
                osu_version,  # "20210520"
                osu_client_hash,
                storyboard_checksum,
                # yyMMddHHmmss
            )
            .encode(),
        ).hexdigest()
