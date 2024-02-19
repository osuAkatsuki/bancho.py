from __future__ import annotations

from enum import IntEnum
from enum import unique

from app.utils import escape_enum
from app.utils import pymysql_encode


@unique
@pymysql_encode(escape_enum)
class MatchWinConditions(IntEnum):
    SCORE = 0
    ACCURACY = 1
    COMBO = 2
    SCORE_V2 = 3


@unique
@pymysql_encode(escape_enum)
class MatchTeamTypes(IntEnum):
    HEAD_TO_HEAD = 0
    TAG_CO_OP = 1
    TEAM_VS = 2
    TAG_TEAM_VS = 3


@unique
@pymysql_encode(escape_enum)
class MatchTeams(IntEnum):
    NEUTRAL = 0
    BLUE = 1
    RED = 2


@unique
@pymysql_encode(escape_enum)
class SlotStatus(IntEnum):
    OPEN = 1
    LOCKED = 2
    NOT_READY = 4
    READY = 8
    NO_MAP = 16
    PLAYING = 32
    COMPLETE = 64
    QUIT = 128

    # HAS_PLAYER = NOT_READY | READY | NO_MAP | PLAYING | COMPLETE
