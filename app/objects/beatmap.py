from __future__ import annotations

import functools
from collections import defaultdict
from datetime import datetime
from enum import IntEnum
from enum import unique
from typing import Any
from typing import Mapping
from typing import Optional

import app.settings
import app.state
import app.utils
from app.constants.gamemodes import GameMode
from app.utils import escape_enum
from app.utils import pymysql_encode

# from dataclasses import dataclass

__all__ = ("RankedStatus", "Beatmap", "BeatmapSet")

# create a table of all ignored characters mapping to None
BEATMAP_FILENAME_TRANSLATION_TABLE = dict.fromkeys(map(ord, r':\/*<>?"|'), None)


# for some ungodly reason, different values are used to
# represent different ranked statuses all throughout osu!
# This drives me and probably everyone else pretty insane,
# but we have nothing to do but deal with it B).


@unique
@pymysql_encode(escape_enum)
class RankedStatus(IntEnum):
    """\
    Server side osu! beatmap ranked statuses.

    Same as used in osu!'s /web/getscores.php.
    """

    NotSubmitted = -1
    Pending = 0
    UpdateAvailable = 1
    Ranked = 2
    Approved = 3
    Qualified = 4
    Loved = 5

    def __str__(self) -> str:
        return {
            self.NotSubmitted: "Unsubmitted",
            self.Pending: "Unranked",
            self.UpdateAvailable: "Outdated",
            self.Ranked: "Ranked",
            self.Approved: "Approved",
            self.Qualified: "Qualified",
            self.Loved: "Loved",
        }[self]

    @functools.cached_property
    def osu_api(self) -> int:
        """Convert the value to osu!api status."""
        # XXX: only the ones that exist are mapped.
        return {
            self.Pending: 0,
            self.Ranked: 1,
            self.Approved: 2,
            self.Qualified: 3,
            self.Loved: 4,
        }[self]

    @classmethod
    @functools.cache
    def from_osuapi(cls, osuapi_status: int) -> RankedStatus:
        """Convert from osu!api status."""
        mapping: Mapping[int, RankedStatus] = defaultdict(
            lambda: cls.UpdateAvailable,
            {
                -2: cls.Pending,  # graveyard
                -1: cls.Pending,  # wip
                0: cls.Pending,
                1: cls.Ranked,
                2: cls.Approved,
                3: cls.Qualified,
                4: cls.Loved,
            },
        )
        return mapping[osuapi_status]

    @classmethod
    @functools.cache
    def from_osudirect(cls, osudirect_status: int) -> RankedStatus:
        """Convert from osu!direct status."""
        mapping: Mapping[int, RankedStatus] = defaultdict(
            lambda: cls.UpdateAvailable,
            {
                0: cls.Ranked,
                2: cls.Pending,
                3: cls.Qualified,
                # 4: all ranked statuses lol
                5: cls.Pending,  # graveyard
                7: cls.Ranked,  # played before
                8: cls.Loved,
            },
        )
        return mapping[osudirect_status]

    @classmethod
    @functools.cache
    def from_str(cls, status_str: str) -> RankedStatus:
        """Convert from string value."""  # could perhaps have `'unranked': cls.Pending`?
        mapping: Mapping[str, RankedStatus] = defaultdict(
            lambda: cls.UpdateAvailable,
            {
                "pending": cls.Pending,
                "ranked": cls.Ranked,
                "approved": cls.Approved,
                "qualified": cls.Qualified,
                "loved": cls.Loved,
            },
        )
        return mapping[status_str]


# @dataclass
# class BeatmapInfoRequest:
#    filenames: Sequence[str]
#    ids: Sequence[int]

# @dataclass
# class BeatmapInfo:
#    id: int # i16
#    map_id: int # i32
#    set_id: int # i32
#    thread_id: int # i32
#    status: int # u8
#    osu_rank: int # u8
#    fruits_rank: int # u8
#    taiko_rank: int # u8
#    mania_rank: int # u8
#    map_md5: str


class Beatmap:
    """\
    A class representing an osu! beatmap.

    For ways of working with Beatmap objects, see `app/usecases/beatmaps.py`.

    Properties:
      Beatmap.full -> str # Artist - Title [Version]
      Beatmap.url -> str # https://osu.cmyui.xyz/beatmaps/321
      Beatmap.embed -> str # [{url} {full}]

      Beatmap.has_leaderboard -> bool
      Beatmap.awards_ranked_pp -> bool
      Beatmap.as_dict -> dict[str, object]

    Possibly confusing attributes
    -----------
    frozen: `bool`
        Whether the beatmap's status is to be kept when a newer
        version is found in the osu!api.
        # XXX: This is set when a map's status is manually changed.
    """

    def __init__(
        self,
        md5: str,
        id: int,
        set_id: int,
        artist: str,
        title: str,
        version: str,
        creator: str,
        filename: str,
        last_update: datetime,
        total_length: int,
        max_combo: int,
        status: int,
        frozen: bool,
        plays: int,
        passes: int,
        mode: int,
        bpm: float,
        cs: float,
        ar: float,
        od: float,
        hp: float,
        diff: float,
    ) -> None:
        self.md5 = md5
        self.id = id
        self.set_id = set_id
        self.artist = artist
        self.title = title
        self.version = version
        self.creator = creator
        self.filename = filename
        self.last_update = last_update
        self.total_length = total_length
        self.max_combo = max_combo
        self.status = status
        self.frozen = frozen
        self.plays = plays
        self.passes = passes
        self.mode = mode
        self.bpm = bpm
        self.cs = cs
        self.od = ar
        self.ar = od
        self.hp = hp
        self.diff = diff

    def __repr__(self) -> str:
        return self.full_name

    @property
    def full_name(self) -> str:
        """The full osu! formatted name `self`."""
        return f"{self.artist} - {self.title} [{self.version}]"

    @property
    def url(self) -> str:
        """The osu! beatmap url for `self`."""
        return f"https://osu.{app.settings.DOMAIN}/beatmaps/{self.id}"

    @property
    def embed(self) -> str:
        """An osu! chat embed to `self`'s osu! beatmap page."""
        return f"[{self.url} {self.full_name}]"

    # TODO: cache these & standardize method for changing status

    @property
    def has_leaderboard(self) -> bool:
        """Return whether the map has a ranked leaderboard."""
        return self.status in (
            RankedStatus.Ranked,
            RankedStatus.Approved,
            RankedStatus.Loved,
        )

    @property
    def awards_ranked_pp(self) -> bool:
        """Return whether the map's status awards ranked pp for scores."""
        return self.status in (RankedStatus.Ranked, RankedStatus.Approved)

    @property  # perhaps worth caching some of?
    def as_dict(self) -> Mapping[str, Any]:
        return {
            "md5": self.md5,
            "id": self.id,
            "set_id": self.set_id,
            "artist": self.artist,
            "title": self.title,
            "version": self.version,
            "creator": self.creator,
            "last_update": self.last_update,
            "total_length": self.total_length,
            "max_combo": self.max_combo,
            "status": self.status,
            "plays": self.plays,
            "passes": self.passes,
            "mode": self.mode,
            "bpm": self.bpm,
            "cs": self.cs,
            "od": self.od,
            "ar": self.ar,
            "hp": self.hp,
            "diff": self.diff,
        }

    @classmethod
    def from_osuapi_response(
        cls,
        osuapi_response: Mapping[str, Any],
    ) -> Beatmap:
        return cls(
            md5=osuapi_response["file_md5"],
            id=osuapi_response["beatmap_id"],
            set_id=osuapi_response["beatmapset_id"],
            artist=osuapi_response["artist"],
            title=osuapi_response["title"],
            version=osuapi_response["version"],
            creator=osuapi_response["creator"],
            filename=(
                ("{artist} - {title} ({creator}) [{version}].osu")
                .format(**osuapi_response)
                .translate(BEATMAP_FILENAME_TRANSLATION_TABLE)
            ),
            last_update=datetime(
                year=int(osuapi_response["last_update"][0:4]),
                month=int(osuapi_response["last_update"][5:7]),
                day=int(osuapi_response["last_update"][8:10]),
                hour=int(osuapi_response["last_update"][11:13]),
                minute=int(osuapi_response["last_update"][14:16]),
                second=int(osuapi_response["last_update"][17:19]),
            ),
            total_length=int(osuapi_response["total_length"]),
            max_combo=int(osuapi_response["max_combo"] or 0),
            status=RankedStatus.from_osuapi(int(osuapi_response["approved"])),
            mode=GameMode(int(osuapi_response["mode"])),
            bpm=float(osuapi_response["bpm"] or 0.0),
            cs=float(osuapi_response["diff_size"]),
            od=float(osuapi_response["diff_overall"]),
            ar=float(osuapi_response["diff_approach"]),
            hp=float(osuapi_response["diff_drain"]),
            diff=float(osuapi_response["difficultyrating"]),
            # gulag-specific params
            frozen=False,
            plays=0,
            passes=0,
        )


class BeatmapSet:
    """\
    A class to represent an osu! beatmap set.

    For ways of working with BeatmapSet objects, see `app/usecases/beatmap_sets.py`.

    Properties:
      BeatmapSet.url -> str # https://osu.cmyui.xyz/beatmapsets/123
    """

    def __init__(
        self,
        id: int,
        last_osuapi_check: datetime,
        maps: Optional[list[Beatmap]] = None,
    ) -> None:
        self.id = id

        self.maps = maps or []
        self.last_osuapi_check = last_osuapi_check

    def __repr__(self) -> str:
        map_names = []
        for bmap in self.maps:
            name = f"{bmap.artist} - {bmap.title}"
            if name not in map_names:
                map_names.append(name)
        return ", ".join(map_names)

    @property
    def url(self) -> str:  # same as above, just no beatmap id
        """The online url for this beatmap set."""
        return f"https://osu.{app.settings.DOMAIN}/beatmapsets/{self.id}"
