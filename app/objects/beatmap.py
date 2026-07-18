from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from typing import Any

import app.settings
from app.constants.beatmap_statuses import RankedStatus
from app.constants.gamemodes import GameMode

# from dataclasses import dataclass

DEFAULT_LAST_UPDATE = datetime(1970, 1, 1)

IGNORED_BEATMAP_CHARS = dict.fromkeys(map(ord, r':\/*<>?"|'), None)


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
    """A domain object representing an osu! beatmap.

    Lookup, caching, persistence, updates, and file downloads are owned by
    ``BeatmapsService``. This object contains beatmap data and derived domain
    properties only.

    Possibly confusing attributes
    -----------
    frozen: `bool`
        Whether the beatmap's status is to be kept when a newer
        version is found in the osu!api.
        # XXX: This is set when a map's status is manually changed.
    """

    def __init__(
        self,
        map_set: BeatmapSet,
        md5: str = "",
        id: int = 0,
        set_id: int = 0,
        artist: str = "",
        title: str = "",
        version: str = "",
        creator: str = "",
        last_update: datetime = DEFAULT_LAST_UPDATE,
        total_length: int = 0,
        max_combo: int = 0,
        status: RankedStatus = RankedStatus.Pending,
        frozen: bool = False,
        plays: int = 0,
        passes: int = 0,
        mode: GameMode = GameMode.VANILLA_OSU,
        bpm: float = 0.0,
        cs: float = 0.0,
        od: float = 0.0,
        ar: float = 0.0,
        hp: float = 0.0,
        diff: float = 0.0,
        filename: str = "",
    ) -> None:
        self.set = map_set

        self.md5 = md5
        self.id = id
        self.set_id = set_id
        self.artist = artist
        self.title = title
        self.version = version
        self.creator = creator
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
        self.od = od
        self.ar = ar
        self.hp = hp
        self.diff = diff
        self.filename = filename

    def __repr__(self) -> str:
        return self.full_name

    @property
    def full_name(self) -> str:
        """The full osu! formatted name `self`."""
        return f"{self.artist} - {self.title} [{self.version}]"

    @property
    def url(self) -> str:
        """The osu! beatmap url for `self`."""
        return f"https://osu.{app.settings.DOMAIN}/b/{self.id}"

    @property
    def embed(self) -> str:
        """An osu! chat embed to `self`'s osu! beatmap page."""
        return f"[{self.url} {self.full_name}]"

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
    def as_dict(self) -> dict[str, object]:
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

    def _parse_from_osuapi_resp(self, osuapi_resp: dict[str, Any]) -> None:
        """Change internal data with the data in osu!api format."""
        # NOTE: `self` is not guaranteed to have any attributes
        #       initialized when this is called.
        self.md5 = osuapi_resp["file_md5"]
        # self.id = int(osuapi_resp['beatmap_id'])
        self.set_id = int(osuapi_resp["beatmapset_id"])

        self.artist, self.title, self.version, self.creator = (
            osuapi_resp["artist"],
            osuapi_resp["title"],
            osuapi_resp["version"],
            osuapi_resp["creator"],
        )

        self.filename = (
            ("{artist} - {title} ({creator}) [{version}].osu")
            .format(**osuapi_resp)
            .translate(IGNORED_BEATMAP_CHARS)
        )

        # quite a bit faster than using dt.strptime.
        _last_update = osuapi_resp["last_update"]
        self.last_update = datetime(
            year=int(_last_update[0:4]),
            month=int(_last_update[5:7]),
            day=int(_last_update[8:10]),
            hour=int(_last_update[11:13]),
            minute=int(_last_update[14:16]),
            second=int(_last_update[17:19]),
        )

        self.total_length = int(osuapi_resp["total_length"])

        if osuapi_resp["max_combo"] is not None:
            self.max_combo = int(osuapi_resp["max_combo"])
        else:
            self.max_combo = 0

        # if a map is 'frozen', we keep its status
        # even after an update from the osu!api.
        if not getattr(self, "frozen", False):
            osuapi_status = int(osuapi_resp["approved"])
            self.status = RankedStatus.from_osuapi(osuapi_status)

        self.mode = GameMode(int(osuapi_resp["mode"]))

        if osuapi_resp["bpm"] is not None:
            self.bpm = float(osuapi_resp["bpm"])
        else:
            self.bpm = 0.0

        self.cs = float(osuapi_resp["diff_size"])
        self.od = float(osuapi_resp["diff_overall"])
        self.ar = float(osuapi_resp["diff_approach"])
        self.hp = float(osuapi_resp["diff_drain"])

        self.diff = float(osuapi_resp["difficultyrating"])


class BeatmapSet:
    """A domain object representing an osu! beatmap set."""

    def __init__(
        self,
        id: int,
        last_osuapi_check: datetime,
        maps: list[Beatmap] | None = None,
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
    def url(self) -> str:
        """The online url for this beatmap set."""
        return f"https://osu.{app.settings.DOMAIN}/s/{self.id}"

    def any_beatmaps_have_official_leaderboards(self) -> bool:
        """Whether all the maps in the set have leaderboards on official servers."""
        leaderboard_having_statuses = (
            RankedStatus.Loved,
            RankedStatus.Ranked,
            RankedStatus.Approved,
        )
        return any(bmap.status in leaderboard_having_statuses for bmap in self.maps)

    def is_cache_expired(self, current_datetime: datetime) -> bool:
        """Whether the cached version of the set is
        expired and needs an update from the osu!api."""
        if not self.maps:
            return True

        # the delta between cache invalidations will increase depending
        # on how long it's been since the map was last updated on osu!
        last_map_update = max(bmap.last_update for bmap in self.maps)
        update_delta = current_datetime - last_map_update

        # with a minimum of 2 hours, add 5 hours per year since its update.
        # the formula for this is subject to adjustment in the future.
        check_delta = timedelta(hours=2 + ((5 / 365) * update_delta.days))

        # it's much less likely that a beatmapset who has beatmaps with
        # leaderboards on official servers will be updated.
        if self.any_beatmaps_have_official_leaderboards():
            check_delta *= 4

        # we'll cache for an absolute maximum of 1 day.
        check_delta = min(check_delta, timedelta(days=1))

        return current_datetime > (self.last_osuapi_check + check_delta)
