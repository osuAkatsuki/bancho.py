from __future__ import annotations

import functools
from collections import defaultdict
from collections.abc import Mapping
from enum import IntEnum
from enum import unique

from app.utils import escape_enum
from app.utils import pymysql_encode


# for some ungodly reason, different values are used to
# represent different ranked statuses all throughout osu!
# This drives me and probably everyone else pretty insane,
# but we have nothing to do but deal with it B).
@unique
@pymysql_encode(escape_enum)
class RankedStatus(IntEnum):
    """Server side osu! beatmap ranked statuses.
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
