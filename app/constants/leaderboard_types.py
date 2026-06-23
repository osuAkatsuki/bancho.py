from __future__ import annotations

from enum import IntEnum
from enum import unique

from app.utils import escape_enum
from app.utils import pymysql_encode


@unique
@pymysql_encode(escape_enum)
class LeaderboardType(IntEnum):
    Local = 0
    Top = 1
    Mods = 2
    Friends = 3
    Country = 4
