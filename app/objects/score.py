from __future__ import annotations

import functools
import hashlib
from datetime import datetime
from enum import IntEnum
from enum import unique
from typing import TYPE_CHECKING

from app.constants.clientflags import ClientFlags
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.constants.score_statuses import SubmissionStatus

if TYPE_CHECKING:
    from app.objects.beatmap import Beatmap
    from app.objects.player import Player


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


class Score:
    """\
    Server side representation of an osu! score; any gamemode.

    Possibly confusing attributes
    -----------
    bmap: `Beatmap | None`
        A beatmap obj representing the osu map.

    player: `Player | None`
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

    prev_best: `Score | None`
        The previous best score before this play was submitted.
        NOTE: just because a score has a `prev_best` attribute does
        mean the score is our best score on the map! the `status`
        value will always be accurate for any score.
    """

    def __init__(self) -> None:
        # TODO: check whether the reamining Optional's should be
        self.id: int | None = None
        self.bmap: Beatmap | None = None
        self.player: Player | None = None

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

        self.rank: int | None = None
        self.prev_best: Score | None = None

    def __repr__(self) -> str:
        # TODO: i really need to clean up my reprs
        try:
            assert self.bmap is not None
            return (
                f"<{self.acc:.2f}% {self.max_combo}x {self.nmiss}M "
                f"#{self.rank} on {self.bmap.full_name} for {self.pp:,.2f}pp>"
            )
        except:
            return super().__repr__()

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
