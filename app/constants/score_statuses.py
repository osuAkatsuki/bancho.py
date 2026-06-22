from __future__ import annotations

from enum import IntEnum
from enum import unique

from app.utils import escape_enum
from app.utils import pymysql_encode


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
