""" api: gulag's public api for developers """
import hashlib
import struct
from pathlib import Path as SystemPath
from typing import AsyncIterator
from typing import Literal
from typing import Optional

import sqlalchemy
import databases.core
from fastapi import APIRouter
from fastapi import Depends
from fastapi import status
from fastapi.param_functions import Query
from fastapi.responses import ORJSONResponse
from fastapi.responses import Response
from fastapi.responses import StreamingResponse
from sqlalchemy.sql.expression import join
from sqlalchemy.sql.expression import select
from sqlalchemy.sql.functions import func

import app.db_models
import app.misc.utils
import app.services
import app.settings
import packets
from app.constants import regexes
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.objects import glob
from app.objects.beatmap import Beatmap


AVATARS_PATH = SystemPath.cwd() / ".data/avatars"
BEATMAPS_PATH = SystemPath.cwd() / ".data/osu"
REPLAYS_PATH = SystemPath.cwd() / ".data/osr"
SCREENSHOTS_PATH = SystemPath.cwd() / ".data/ss"

router = APIRouter(prefix="/api", tags=["Gulag API"])


# NOTE: the api is still under design and is subject to change.
# to keep up with breaking changes, please either join our discord,
# or keep up with changes to https://github.com/JKBGL/gulag-api-docs.

# Unauthorized (no api key required)
# GET /api/get_player_count: return total registered & online player counts.
# GET /api/get_player_info: return info or stats for a given player.
# GET /api/get_player_status: return a player's current status, if online.
# GET /api/get_player_scores: return a list of best or recent scores for a given player.
# GET /api/get_player_most_played: return a list of maps most played by a given player.
# GET /api/get_map_info: return information about a given beatmap.
# GET /api/get_map_scores: return the best scores for a given beatmap & mode.
# GET /api/get_score_info: return information about a given score.
# GET /api/get_replay: return the file for a given replay (with or without headers).
# GET /api/get_match: return information for a given multiplayer match.
# GET /api/get_leaderboard: return the top players for a given mode & sort condition

# Authorized (requires valid api key, passed as 'Authorization' header)
# NOTE: authenticated handlers may have privilege requirements.

# [Normal]
# GET /api/calculate_pp: calculate & return pp for a given beatmap.
# POST/PUT /api/set_avatar: Update the tokenholder's avatar to a given file.

# TODO handlers
# GET /api/get_friends: return a list of the player's friends.
# POST/PUT /api/set_player_info: update user information (updates whatever received).

DATETIME_OFFSET = 0x89F7FF5F7B58000
SCOREID_BORDERS = tuple((((1 << 63) - 1) // 3) * i for i in range(1, 4))

# TODO: move this into utils?
async def acquire_db_conn() -> AsyncIterator[databases.core.Connection]:
    """Decorator to acquire a database connection for a handler."""
    async with app.services.database.connection() as conn:
        yield conn


@router.get("/api/get_player_count")
async def api_get_player_count(
    db_conn: databases.core.Connection = Depends(acquire_db_conn),
) -> Response:
    """Get the current amount of online players."""
    # TODO: perhaps add peak(s)? (24h, 5d, 3w, etc.)
    # NOTE: -1 is for the bot, and will have to change
    # if we ever make some sort of bot creation system.
    total_users = await db_conn.fetch_val(
        app.db_models.users.select(func.count()),
        column=0,
    )

    return ORJSONResponse(
        {
            "status": "success",
            "counts": {
                "online": len(glob.players.unrestricted) - 1,
                "total": total_users,
            },
        },
    )


@router.get("/api/get_player_info")
async def api_get_player_info(
    scope: Literal["stats", "info", "all"],
    username: Optional[str] = Query(..., alias="name", regex=regexes.USERNAME.pattern),
    user_id: Optional[int] = Query(..., alias="id", ge=3, le=2_147_483_647),
    db_conn: databases.core.Connection = Depends(acquire_db_conn),
) -> Response:
    """Return information about a given player."""
    if not (username or user_id) or (username and user_id):
        return ORJSONResponse(
            {"status": "Must provide either id OR name!"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # get user info from username or user id
    if username:
        user_info = await db_conn.fetch_one(
            select(
                [
                    app.db_models.users.c.id,
                    app.db_models.users.c.name,
                    app.db_models.users.c.safe_name,
                    app.db_models.users.c.priv,
                    app.db_models.users.c.country,
                    app.db_models.users.c.silence_end,
                ],
            ).where(app.db_models.users.c.safe_name == username.lower()),
        )
    else:  # if user_id
        user_info = await db_conn.fetch_one(
            select(
                [
                    app.db_models.users.c.id,
                    app.db_models.users.c.name,
                    app.db_models.users.c.safe_name,
                    app.db_models.users.c.priv,
                    app.db_models.users.c.country,
                    app.db_models.users.c.silence_end,
                ],
            ).where(app.db_models.users.c.userid == user_id),
        )

    if user_info is None:
        return ORJSONResponse(
            {"status": "Player not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    resolved_user_id: int = user_info["id"]
    resolved_country: str = user_info["country"]

    api_data = {}

    # fetch user's info if requested
    if scope in ("info", "all"):
        api_data["info"] = user_info

    # fetch user's stats if requested
    if scope in ("stats", "all"):
        # get all regular stats
        rows = await db_conn.fetch_all(
            select(
                [
                    app.db_models.stats.c.tscore,
                    app.db_models.stats.c.rscore,
                    app.db_models.stats.c.pp,
                    app.db_models.stats.c.plays,
                    app.db_models.stats.c.playtime,
                    app.db_models.stats.c.acc,
                    app.db_models.stats.c.max_combo,
                    app.db_models.stats.c.xh_count,
                    app.db_models.stats.c.x_count,
                    app.db_models.stats.c.sh_count,
                    app.db_models.stats.c.s_count,
                    app.db_models.stats.c.a_count,
                ],
            ).where(app.db_models.stats.c.userid == resolved_user_id),
        )

        for idx, mode_stats in enumerate([dict(row) for row in rows]):
            rank = await glob.redis.zrevrank(
                f"gulag:leaderboard:{idx}",
                resolved_user_id,
            )
            mode_stats["rank"] = rank + 1 if rank is not None else 0

            country_rank = await glob.redis.zrevrank(
                f"gulag:leaderboard:{idx}:{resolved_country}",
                resolved_user_id,
            )
            mode_stats["country_rank"] = (
                country_rank + 1 if country_rank is not None else 0
            )

        api_data["stats"] = rows

    return ORJSONResponse({"status": "success", "player": api_data})


@router.get("/api/get_player_status")
async def api_get_player_status(
    username: Optional[str] = Query(..., alias="name", regex=regexes.USERNAME.pattern),
    user_id: Optional[int] = Query(..., alias="id", ge=3, le=2_147_483_647),
    db_conn: databases.core.Connection = Depends(acquire_db_conn),
) -> Response:
    """Return a players current status, if they are online."""
    if username and user_id:
        return ORJSONResponse(
            {"status": "Must provide either id OR name!"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if username:
        player = glob.players.get(name=username)
    elif user_id:
        player = glob.players.get(id=user_id)
    else:
        return ORJSONResponse(
            {"status": "Must provide either id OR name!"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if not player:
        # no such player online, return their last seen time if they exist in sql

        if username:
            row = await db_conn.fetch_one(
                app.db_models.users.select(app.db_models.users.c.latest_activity).where(
                    app.db_models.users.c.safe_name == username.lower(),
                ),
            )
        else:  # if user_id
            row = await db_conn.fetch_one(
                app.db_models.users.select(app.db_models.users.c.latest_activity).where(
                    app.db_models.users.c.id == user_id,
                ),
            )

        if not row:
            return ORJSONResponse(
                {"status": "Player not found."},
                status_code=status.HTTP_404_NOT_FOUND,
            )

        return ORJSONResponse(
            {
                "status": "success",
                "player_status": {"online": False, "last_seen": row["latest_activity"]},
            },
        )

    if player.status.map_md5:
        bmap = await Beatmap.from_md5(player.status.map_md5)
    else:
        bmap = None

    return ORJSONResponse(
        {
            "status": "success",
            "player_status": {
                "online": True,
                "login_time": player.login_time,
                "status": {
                    "action": int(player.status.action),
                    "info_text": player.status.info_text,
                    "mode": int(player.status.mode),
                    "mods": int(player.status.mods),
                    "beatmap": bmap.as_dict if bmap else None,
                },
            },
        },
    )


@router.get("/api/get_player_scores")
async def api_get_player_scores(
    scope: Literal["recent", "best"],
    username: Optional[str] = Query(..., alias="name", regex=regexes.USERNAME.pattern),
    user_id: Optional[int] = Query(..., alias="id", ge=3, le=2_147_483_647),
    mode_arg: Optional[int] = Query(..., alias="mode", ge=0, le=7),
    mods_arg: Optional[str] = Query(..., alias="mods"),
    limit: Optional[int] = Query(..., ge=1, le=100),
    include_loved: Optional[int] = Query(..., ge=0, le=1),
    db_conn: databases.core.Connection = Depends(acquire_db_conn),
) -> Response:
    """Return a list of a given user's recent/best scores."""
    if username and user_id:
        return ORJSONResponse(
            {"status": "Must provide either id OR name!"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if username:
        player = await glob.players.from_cache_or_sql(name=username)
    elif user_id:
        player = await glob.players.from_cache_or_sql(id=user_id)
    else:
        return ORJSONResponse(
            {"status": "Must provide either id OR name!"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if not player:
        return ORJSONResponse(
            {"status": "Player not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if mode_arg is not None:
        mode = GameMode(mode_arg)
    else:
        mode = GameMode.VANILLA_OSU

    if mods_arg is not None:
        if mods_arg[0] in ("~", "="):  # weak/strong equality
            strong_equality = mods_arg[0] == "="
            mods_arg = mods_arg[1:]
        else:  # use strong as default
            strong_equality = True

        if mods_arg.isdecimal():
            # parse from int form
            mods = Mods(int(mods_arg))
        else:
            # parse from string form
            mods = Mods.from_modstr(mods_arg)
    else:
        mods = None

    if limit is None:
        limit = 25

    # build sql query & fetch info

    alchemy_table = getattr(app.db_models, mode.scores_table)

    params = [
        alchemy_table.c.userid == player.id,
        alchemy_table.c.mode == mode.as_vanilla,
    ]

    if mods is not None:
        if strong_equality:  # type: ignore
            params.append(alchemy_table.c.mods & mods == mods)
        else:
            params.append(alchemy_table.c.mods & mods != 0)

    if scope == "best":
        include_loved = include_loved is not None and include_loved == 1

        allowed_statuses = [2, 3]

        if include_loved:
            allowed_statuses.append(5)

        params.append(
            alchemy_table.c.status == 2
            and app.db_models.maps.c.status in allowed_statuses,
        )
        sort = getattr(alchemy_table.c, "pp")
    else:
        sort = getattr(alchemy_table.c, "play_time")

    # fetch & return info from sql
    maps_join = join(
        alchemy_table,
        app.db_models.maps,
        alchemy_table.c.map_md5 == app.db_models.maps.c.md5,
    )
    res = await db_conn.fetch_all(
        select(
            [
                alchemy_table.c.id,
                alchemy_table.c.map_md5,
                alchemy_table.c.score,
                alchemy_table.c.pp,
                alchemy_table.c.acc,
                alchemy_table.c.max_combo,
                alchemy_table.c.mods,
                alchemy_table.c.n300,
                alchemy_table.c.n100,
                alchemy_table.c.n50,
                alchemy_table.c.nmiss,
                alchemy_table.c.ngeki,
                alchemy_table.c.nkatu,
                alchemy_table.c.grade,
                alchemy_table.c.status,
                alchemy_table.c.mode,
                alchemy_table.c.play_time,
                alchemy_table.c.time_elapsed,
                alchemy_table.c.perfect,
            ],
        )
        .select_from(maps_join)
        .where(sqlalchemy.and_(*params))
        .order_by(sort.desc())
        .limit(limit),
    )

    for row in res:
        bmap = await Beatmap.from_md5(row.pop("map_md5"))
        row["beatmap"] = bmap.as_dict if bmap else None

    player_info = {
        "id": player.id,
        "name": player.name,
        "clan": {"id": player.clan.id, "name": player.clan.name, "tag": player.clan.tag}
        if player.clan
        else None,
    }

    return ORJSONResponse({"status": "success", "scores": res, "player": player_info})


@router.get("/api/get_player_most_played")
async def api_get_player_most_played(
    id: Optional[int] = Query(..., alias="id", ge=3, le=2_147_483_647),
    username: Optional[str] = Query(..., alias="name", regex=regexes.USERNAME.pattern),
    mode_arg: Optional[int] = Query(..., alias="mode", ge=0, le=7),
    limit: Optional[int] = Query(..., ge=1, le=100),
    db_conn: databases.core.Connection = Depends(acquire_db_conn),
) -> Response:
    """Return the most played beatmaps of a given player."""
    # NOTE: this will almost certainly not scale well, lol.

    if id is not None:
        p = await glob.players.from_cache_or_sql(id=id)
    elif username is not None:
        p = await glob.players.from_cache_or_sql(name=username)
    else:
        return ORJSONResponse(
            {"status": "Must provide either id or name."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if not p:
        return ORJSONResponse(
            {"status": "Player not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # parse args (mode, limit)

    if mode_arg is not None:
        mode = GameMode(mode_arg)
    else:
        mode = GameMode.VANILLA_OSU

    if limit is None:
        limit = 25

    # fetch & return info from sql
    alchemy_table = getattr(app.db_models, mode.scores_table)
    maps_join = join(
        alchemy_table,
        app.db_models.maps,
        alchemy_table.c.map_md5 == app.db_models.maps.c.md5,
    )
    res = await db_conn.fetch_all(
        select(
            [
                app.db_models.maps.c.md5,
                app.db_models.maps.c.id,
                app.db_models.maps.c.set_id,
                app.db_models.maps.c.status,
                app.db_models.maps.c.artist,
                app.db_models.maps.c.title,
                app.db_models.maps.c.version,
                app.db_models.maps.c.creator,
                func.count().label("plays"),
            ],
        )
        .select_from(maps_join)
        .where(
            sqlalchemy.and_(
                alchemy_table.c.userid == p.id,
                alchemy_table.c.mode == mode.as_vanilla,
            ),
        )
        .group_by(alchemy_table.c.map_md5)
        .order_by(func.count().desc())
        .limit(limit),
    )

    return ORJSONResponse({"status": "success", "maps": res})


@router.get("/api/get_map_info")
async def api_get_map_info(
    id: Optional[int] = Query(..., alias="id", ge=3, le=2_147_483_647),
    md5: Optional[str] = Query(..., alias="md5", min_length=32, max_length=32),
) -> Response:
    """Return information about a given beatmap."""
    if id is not None:
        bmap = await Beatmap.from_bid(id)
    elif md5 is not None:
        bmap = await Beatmap.from_md5(md5)
    else:
        return ORJSONResponse(
            {"status": "Must provide either id or md5!"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if not bmap:
        return ORJSONResponse(
            {"status": "Map not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return ORJSONResponse({"status": "success", "map": bmap.as_dict})


@router.get("/api/get_map_scores")
async def api_get_map_scores(
    scope: Literal["recent", "best"],
    id: Optional[int] = Query(..., alias="id", ge=3, le=2_147_483_647),
    md5: Optional[str] = Query(..., alias="md5", min_length=32, max_length=32),
    mode_arg: Optional[int] = Query(..., alias="mode", ge=0, le=7),
    mods_arg: Optional[str] = Query(..., alias="mods"),
    limit: Optional[int] = Query(..., ge=1, le=100),
    db_conn: databases.core.Connection = Depends(acquire_db_conn),
):
    """Return the top n scores on a given beatmap."""
    if id is not None:
        bmap = await Beatmap.from_bid(id)
    elif md5 is not None:
        bmap = await Beatmap.from_md5(md5)
    else:
        return ORJSONResponse(
            {"status": "Must provide either id or md5!"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if not bmap:
        return ORJSONResponse(
            {"status": "Map not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # parse args (scope, mode, mods, limit)

    if mode_arg is not None:
        mode = GameMode(mode_arg)
    else:
        mode = GameMode.VANILLA_OSU

    if mods_arg is not None:
        if mods_arg[0] in ("~", "="):  # weak/strong equality
            strong_equality = mods_arg[0] == "="
            mods_arg = mods_arg[1:]
        else:  # use strong as default
            strong_equality = True

        if mods_arg.isdecimal():
            # parse from int form
            mods = Mods(int(mods_arg))
        else:
            # parse from string form
            mods = Mods.from_modstr(mods_arg)
    else:
        mods = None

    if limit is None:
        limit = 50

    # NOTE: userid will eventually become player_id,
    # along with everywhere else in the codebase.
    alchemy_table = getattr(app.db_models, mode.scores_table)

    params = [
        alchemy_table.c.map_md5 == bmap.md5,
        alchemy_table.c.mode == mode.as_vanilla,
    ]

    if mods is not None:
        if strong_equality:  # type: ignore
            params.append(alchemy_table.c.mods & mods == mods)
        else:
            params.append(alchemy_table.c.mods & mods != 0)

    # unlike /api/get_player_scores, we'll sort by score/pp depending
    # on the mode played, since we want to replicated leaderboards.
    if scope == "best":
        sort = getattr(alchemy_table.c, "pp" if mode >= GameMode.RELAX_OSU else "score")
    else:  # recent
        sort = getattr(alchemy_table.c, "play_time")

    user_join = join(
        alchemy_table,
        app.db_models.users,
        alchemy_table.c.userid == app.db_models.users.c.id,
    )
    user_clan_join = join(
        user_join,
        app.db_models.clans,
        app.db_models.users.c.clan_id == app.db_models.clans.c.id,
    )
    res = await db_conn.fetch_all(
        select(
            [
                alchemy_table.c.map_md5,
                alchemy_table.c.score,
                alchemy_table.c.pp,
                alchemy_table.c.acc,
                alchemy_table.c.max_combo,
                alchemy_table.c.mods,
                alchemy_table.c.n300,
                alchemy_table.c.n100,
                alchemy_table.c.n50,
                alchemy_table.c.nmiss,
                alchemy_table.c.ngeki,
                alchemy_table.c.nkatu,
                alchemy_table.c.grade,
                alchemy_table.c.status,
                alchemy_table.c.mode,
                alchemy_table.c.play_time,
                alchemy_table.c.time_elapsed,
                alchemy_table.c.userid,
                alchemy_table.c.perfect,
                app.db_models.users.c.name.label("player_name"),
                app.db_models.clans.c.id.label("clan_id"),
                app.db_models.clans.c.name.label("clan_name"),
                app.db_models.clans.c.tag.label("clan_tag"),
            ],
        )
        .select_from(user_clan_join)
        .where(sqlalchemy.and_(*params))
        .order_by(sort.desc())
        .limit(limit),
    )

    return ORJSONResponse({"status": "success", "scores": res})


@router.get("/api/get_score_info")
async def api_get_score_info(
    score_id: int = Query(..., alias="id", ge=0),
    db_conn: databases.core.Connection = Depends(acquire_db_conn),
) -> Response:
    """Return information about a given score."""

    if SCOREID_BORDERS[0] > score_id >= 1:
        scores_table = "scores_vn"
    elif SCOREID_BORDERS[1] > score_id >= SCOREID_BORDERS[0]:
        scores_table = "scores_rx"
    elif SCOREID_BORDERS[2] > score_id >= SCOREID_BORDERS[1]:
        scores_table = "scores_ap"
    else:
        return ORJSONResponse(
            {"status": "Invalid score id."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    alchemy_table = getattr(app.db_models, scores_table)
    res = await db_conn.fetch_one(
        select(
            [
                alchemy_table.c.map_md5,
                alchemy_table.c.score,
                alchemy_table.c.pp,
                alchemy_table.c.acc,
                alchemy_table.c.max_combo,
                alchemy_table.c.mods,
                alchemy_table.c.n300,
                alchemy_table.c.n100,
                alchemy_table.c.n50,
                alchemy_table.c.nmiss,
                alchemy_table.c.ngeki,
                alchemy_table.c.nkatu,
                alchemy_table.c.grade,
                alchemy_table.c.status,
                alchemy_table.c.mode,
                alchemy_table.c.play_time,
                alchemy_table.c.time_elapsed,
                alchemy_table.c.perfect,
            ],
        ).where(alchemy_table.c.id == score_id),
    )

    if not res:
        return ORJSONResponse(
            {"status": "Score not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return ORJSONResponse({"status": "success", "score": res})


@router.get("/api/get_replay")
async def api_get_replay(
    score_id: int = Query(..., alias="id", ge=0),
    include_headers: Optional[str] = Query(...),
    db_conn: databases.core.Connection = Depends(acquire_db_conn),
) -> Response:
    """Return a given replay (including headers)."""
    if SCOREID_BORDERS[0] > score_id >= 1:
        scores_table = "scores_vn"
    elif SCOREID_BORDERS[1] > score_id >= SCOREID_BORDERS[0]:
        scores_table = "scores_rx"
    elif SCOREID_BORDERS[2] > score_id >= SCOREID_BORDERS[1]:
        scores_table = "scores_ap"
    else:
        return ORJSONResponse(
            {"status": "Invalid score id."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # fetch replay file & make sure it exists
    replay_file = REPLAYS_PATH / f"{score_id}.osr"
    if not replay_file.exists():
        return ORJSONResponse(
            {"status": "Replay not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # read replay frames from file
    raw_replay_data = replay_file.read_bytes()

    if include_headers and include_headers.lower() == "false":
        return StreamingResponse(
            raw_replay_data,
            media_type="application/octet-stream",
            headers={
                "Content-Description": "File Transfer",
                # TODO: should we do the query to fetch
                # info for content-disposition for this..?
            },
        )

    # add replay headers from sql
    # TODO: osu_version & life graph in scores tables?
    alchemy_table = getattr(app.db_models, scores_table)
    users_join = join(
        alchemy_table,
        app.db_models.users,
        alchemy_table.c.userid == app.db_models.users.c.id,
    )
    users_maps_join = join(
        users_join,
        app.db_models.maps,
        alchemy_table.c.map_md5 == app.db_models.maps.c.md5,
    )

    res = await db_conn.fetch_one(
        select(
            [
                app.db_models.users.c.name.label("username"),
                app.db_models.maps.c.md5.label("map_md5"),
                app.db_models.maps.c.artist,
                app.db_models.maps.c.title,
                app.db_models.maps.c.version,
                alchemy_table.c.mode,
                alchemy_table.c.n300,
                alchemy_table.c.n100,
                alchemy_table.c.n50,
                alchemy_table.c.ngeki,
                alchemy_table.c.nkatu,
                alchemy_table.c.nmiss,
                alchemy_table.c.score,
                alchemy_table.c.max_combo,
                alchemy_table.c.perfect,
                alchemy_table.c.mods,
                alchemy_table.c.play_time,
            ],
        )
        .select_from(users_maps_join)
        .where(alchemy_table.c.id == score_id),
    )

    if not res:
        # score not found in sql
        return ORJSONResponse(
            {"status": "Score not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )  # but replay was?

    # generate the replay's hash
    replay_md5 = hashlib.md5(
        "{}p{}o{}o{}t{}a{}r{}e{}y{}o{}u{}{}{}".format(
            res["n100"] + res["n300"],
            res["n50"],
            res["ngeki"],
            res["nkatu"],
            res["nmiss"],
            res["map_md5"],
            res["max_combo"],
            str(res["perfect"] == 1),
            res["username"],
            res["score"],
            0,  # TODO: rank
            res["mods"],
            "True",  # TODO: ??
        ).encode(),
    ).hexdigest()

    # create a buffer to construct the replay output
    replay_data = bytearray()

    # pack first section of headers.
    replay_data += struct.pack("<Bi", res["mode"], 20200207)  # TODO: osuver
    replay_data += packets.write_string(res["map_md5"])
    replay_data += packets.write_string(res["username"])
    replay_data += packets.write_string(replay_md5)
    replay_data += struct.pack(
        "<hhhhhhihBi",
        res["n300"],
        res["n100"],
        res["n50"],
        res["ngeki"],
        res["nkatu"],
        res["nmiss"],
        res["score"],
        res["max_combo"],
        res["perfect"],
        res["mods"],
    )
    replay_data += b"\x00"  # TODO: hp graph

    timestamp = int(res["play_time"].timestamp() * 1e7)
    replay_data += struct.pack("<q", timestamp + DATETIME_OFFSET)

    # pack the raw replay data into the buffer
    replay_data += struct.pack("<i", len(raw_replay_data))
    replay_data += raw_replay_data

    # pack additional info info buffer.
    replay_data += struct.pack("<q", score_id)

    # NOTE: target practice sends extra mods, but
    # can't submit scores so should not be a problem.

    # stream data back to the client
    return StreamingResponse(
        replay_data,
        media_type="application/octet-stream",
        headers={
            "Content-Description": "File Transfer",
            "Content-Disposition": (
                'attachment; filename="{username} - '
                "{artist} - {title} [{version}] "
                '({play_time:%Y-%m-%d}).osr"'
            ).format(**res),
        },
    )


@router.get("/api/get_match")
async def api_get_match(
    match_id: int = Query(..., alias="id", ge=1, le=64),
) -> Response:
    """Return information of a given multiplayer match."""
    # TODO: eventually, this should contain recent score info.

    if not (match := glob.matches[match_id]):
        return ORJSONResponse(
            {"status": "Match not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return ORJSONResponse(
        {
            "status": "success",
            "match": {
                "name": match.name,
                "mode": match.mode.as_vanilla,
                "mods": int(match.mods),
                "seed": match.seed,
                "host": {"id": match.host.id, "name": match.host.name},
                "refs": [{"id": p.id, "name": p.name} for p in match.refs],
                "in_progress": match.in_progress,
                "is_scrimming": match.is_scrimming,
                "map": {
                    "id": match.map_id,
                    "md5": match.map_md5,
                    "name": match.map_name,
                },
                "active_slots": {
                    str(idx): {
                        "loaded": slot.loaded,
                        "mods": int(slot.mods),
                        "player": {"id": slot.player.id, "name": slot.player.name},
                        "skipped": slot.skipped,
                        "status": int(slot.status),
                        "team": int(slot.team),
                    }
                    for idx, slot in enumerate(match.slots)
                    if slot.player
                },
            },
        },
    )


@router.get("/api/get_leaderboard")
async def api_get_global_leaderboard(
    sort: Literal["tscore", "rscore", "pp", "acc"],
    mode_arg: Optional[int] = Query(..., alias="mode", ge=0, le=7),
    limit: int = Query(..., alias="limit", ge=1, le=100),
    db_conn: databases.core.Connection = Depends(acquire_db_conn),
) -> Response:
    if mode_arg is not None:
        mode = GameMode(mode_arg)
    else:
        mode = GameMode.VANILLA_OSU

    if limit is None:
        limit = 25

    if sort is None:
        sort = "pp"

    alchemy_sort = getattr(app.db_models.stats.c, sort)
    users_join = join(
        app.db_models.stats,
        app.db_models.users,
        app.db_models.stats.c.id == app.db_models.users.c.id,
    )
    users_clans_join = join(
        users_join,
        app.db_models.clans,
        app.db_models.clans.c.id == app.db_models.users.c.clan_id,
    )
    res = await db_conn.fetch_all(
        select(
            [
                app.db_models.users.c.id.label("player_id"),
                app.db_models.users.c.name,
                app.db_models.users.c.country,
                app.db_models.stats.c.tscore,
                app.db_models.stats.c.rscore,
                app.db_models.stats.c.pp,
                app.db_models.stats.c.plays,
                app.db_models.stats.c.playtime,
                app.db_models.stats.c.acc,
                app.db_models.stats.c.max_combo,
                app.db_models.stats.c.xh_count,
                app.db_models.stats.c.x_count,
                app.db_models.stats.c.sh_count,
                app.db_models.stats.c.s_count,
                app.db_models.stats.c.a_count,
                app.db_models.clans.c.id.label("clan_id"),
                app.db_models.clans.c.name.label("clan_name"),
                app.db_models.clans.c.tag.label("clan_tag"),
            ],
        )
        .select_from(users_clans_join)
        .where(
            sqlalchemy.and_(
                app.db_models.stats.c.mode == mode.value,
                app.db_models.users.c.priv & 1,
                alchemy_sort > 0,
            ),
        )
        .order_by(alchemy_sort.desc())
        .limit(limit),
    )

    return ORJSONResponse({"status": "success", "leaderboard": res})


# def requires_api_key(f: Callable) -> Callable:
#     @wraps(f)
#     async def wrapper():
#         conn.resp_headers["Content-Type"] = "application/json"
#         if "Authorization" not in conn.headers:
#             return ORJSONResponse(
#                 {"status": "Must provide authorization token."},
#                 status_code=status.HTTP_400_BAD_REQUEST,
#             )

#         api_key = conn.headers["Authorization"]

#         if api_key not in glob.api_keys:
#             return ORJSONResponse(
#                 {"status": "Unknown authorization token."},
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#             )

#         # get player from api token
#         player_id = glob.api_keys[api_key]
#         p = await glob.players.from_cache_or_sql(id=player_id)

#         return await f(conn, p)

#     return wrapper


# # NOTE: `Content-Type = application/json` is applied in the above decorator
# #                                         for the following api handlers.


# @router.put("/api/set_avatar")
# @requires_api_key
# async def api_set_avatar(p: "Player"):
#     """Update the tokenholder's avatar to a given file."""
#     if "avatar" not in conn.files:
#         return ORJSONResponse(
#             {"status": "must provide avatar file."},
#             status_code=status.HTTP_400_BAD_REQUEST,
#         )

#     ava_file = conn.files["avatar"]

#     # block files over 4MB
#     if len(ava_file) > (4 * 1024 * 1024):
#         return ORJSONResponse(
#             {"status": "avatar file too large (max 4MB)."},
#             status_code=status.HTTP_400_BAD_REQUEST,
#         )

#     if ava_file[6:10] in (b"JFIF", b"Exif"):
#         ext = "jpeg"
#     elif ava_file.startswith(b"\211PNG\r\n\032\n"):
#         ext = "png"
#     else:
#         return ORJSONResponse(
#             {"status": "invalid file type."},
#             status_code=status.HTTP_400_BAD_REQUEST,
#         )

#     # write to the avatar file
#     (AVATARS_PATH / f"{p.id}.{ext}").write_bytes(ava_file)
#     return ORJSONResponse({"status": "success."})
