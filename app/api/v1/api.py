""" api: bancho.py's developer api for interacting with server state """

from __future__ import annotations

import hashlib
import struct
from pathlib import Path as SystemPath
from typing import Literal

from fastapi import APIRouter
from fastapi import Depends
from fastapi import status
from fastapi.param_functions import Query
from fastapi.responses import ORJSONResponse
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials as HTTPCredentials
from fastapi.security import HTTPBearer

import app.packets
import app.state
import app.usecases.performance
from app.constants import regexes
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.objects.beatmap import Beatmap
from app.objects.beatmap import ensure_osu_file_is_available
from app.repositories import clans as clans_repo
from app.repositories import scores as scores_repo
from app.repositories import stats as stats_repo
from app.repositories import tourney_pool_maps as tourney_pool_maps_repo
from app.repositories import tourney_pools as tourney_pools_repo
from app.repositories import users as users_repo
from app.usecases.performance import ScoreParams

AVATARS_PATH = SystemPath.cwd() / ".data/avatars"
BEATMAPS_PATH = SystemPath.cwd() / ".data/osu"
REPLAYS_PATH = SystemPath.cwd() / ".data/osr"
SCREENSHOTS_PATH = SystemPath.cwd() / ".data/ss"


router = APIRouter()
oauth2_scheme = HTTPBearer(auto_error=False)

# NOTE: the api is still under design and is subject to change.
# to keep up with breaking changes, please either join our discord,
# or keep up with changes to https://github.com/JKBGL/gulag-api-docs.

# Unauthorized (no api key required)
# GET /search_players: returns a list of matching users, based on a passed string, sorted by ascending ID.
# GET /get_player_count: return total registered & online player counts.
# GET /get_player_info: return info or stats for a given player.
# GET /get_player_status: return a player's current status, if online.
# GET /get_player_scores: return a list of best or recent scores for a given player.
# GET /get_player_most_played: return a list of maps most played by a given player.
# GET /get_map_info: return information about a given beatmap.
# GET /get_map_scores: return the best scores for a given beatmap & mode.
# GET /get_score_info: return information about a given score.
# GET /get_replay: return the file for a given replay (with or without headers).
# GET /get_match: return information for a given multiplayer match.
# GET /get_leaderboard: return the top players for a given mode & sort condition

# Authorized (requires valid api key, passed as 'Authorization' header)
# NOTE: authenticated handlers may have privilege requirements.

# [Normal]
# GET /calculate_pp: calculate & return pp for a given beatmap.
# POST/PUT /set_avatar: Update the tokenholder's avatar to a given file.

DATETIME_OFFSET = 0x89F7FF5F7B58000


@router.get("/calculate_pp")
async def api_calculate_pp(
    token: HTTPCredentials = Depends(oauth2_scheme),
    beatmap_id: int = Query(None, alias="id", min=0, max=2_147_483_647),
    nkatu: int = Query(None, max=2_147_483_647),
    ngeki: int = Query(None, max=2_147_483_647),
    n100: int = Query(None, max=2_147_483_647),
    n50: int = Query(None, max=2_147_483_647),
    misses: int = Query(0, max=2_147_483_647),
    mods: int = Query(0, min=0, max=2_147_483_647),
    mode: int = Query(0, min=0, max=11),
    combo: int = Query(None, max=2_147_483_647),
    acclist: list[float] = Query([100, 99, 98, 95], alias="acc"),
) -> Response:
    """Calculates the PP of a specified map with specified score parameters."""

    if token is None or app.state.sessions.api_keys.get(token.credentials) is None:
        return ORJSONResponse(
            {"status": "Invalid API key."},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    beatmap = await Beatmap.from_bid(beatmap_id)
    if not beatmap:
        return ORJSONResponse(
            {"status": "Beatmap not found."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    osu_file_available = await ensure_osu_file_is_available(
        beatmap.id,
        expected_md5=beatmap.md5,
    )
    if not osu_file_available:
        return ORJSONResponse(
            {"status": "Beatmap file could not be fetched."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    scores = []

    if all(x is None for x in [ngeki, nkatu, n100, n50]):
        scores = [
            ScoreParams(GameMode(mode).as_vanilla, mods, combo, acc, nmiss=misses)
            for acc in acclist
        ]
    else:
        scores.append(
            ScoreParams(
                GameMode(mode).as_vanilla,
                mods,
                combo,
                ngeki=ngeki or 0,
                nkatu=nkatu or 0,
                n100=n100 or 0,
                n50=n50 or 0,
                nmiss=misses,
            ),
        )

    results = app.usecases.performance.calculate_performances(
        str(BEATMAPS_PATH / f"{beatmap.id}.osu"),
        scores,
    )

    # "Inject" the accuracy into the list of results
    final_results = [
        performance_result | {"accuracy": score.acc}
        for performance_result, score in zip(results, scores)
    ]

    return ORJSONResponse(
        # XXX: change the output type based on the inputs from user
        (
            final_results
            if all(x is None for x in [ngeki, nkatu, n100, n50])
            else final_results[0]
        ),
        status_code=status.HTTP_200_OK,  # a list via the acclist parameter or a single score via n100 and n50
    )


@router.get("/search_players")
async def api_search_players(
    search: str | None = Query(None, alias="q", min=2, max=32),
) -> Response:
    """Search for users on the server by name."""
    rows = await app.state.services.database.fetch_all(
        "SELECT id, name "
        "FROM users "
        "WHERE name LIKE COALESCE(:name, name) "
        "AND priv & 3 = 3 "
        "ORDER BY id ASC",
        {"name": f"%{search}%" if search is not None else None},
    )

    return ORJSONResponse(
        {
            "status": "success",
            "results": len(rows),
            "result": [dict(row) for row in rows],
        },
    )


@router.get("/get_player_count")
async def api_get_player_count() -> Response:
    """Get the current amount of online players."""
    return ORJSONResponse(
        {
            "status": "success",
            "counts": {
                # -1 for the bot, who is always online
                "online": len(app.state.sessions.players.unrestricted) - 1,
                "total": await users_repo.fetch_count(),
            },
        },
    )


@router.get("/get_player_info")
async def api_get_player_info(
    scope: Literal["stats", "info", "all"],
    user_id: int | None = Query(None, alias="id", ge=3, le=2_147_483_647),
    username: str | None = Query(None, alias="name", pattern=regexes.USERNAME.pattern),
) -> Response:
    """Return information about a given player."""
    if not (username or user_id) or (username and user_id):
        return ORJSONResponse(
            {"status": "Must provide either id OR name!"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # get user info from username or user id
    if username:
        user_info = await users_repo.fetch_one(name=username)
    else:  # if user_id
        user_info = await users_repo.fetch_one(id=user_id)

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
        api_data["info"] = dict(user_info)

    # fetch user's stats if requested
    if scope in ("stats", "all"):
        api_data["stats"] = {}

        # get all stats
        all_stats = await stats_repo.fetch_many(player_id=resolved_user_id)

        for mode_stats in all_stats:
            rank = await app.state.services.redis.zrevrank(
                f"bancho:leaderboard:{mode_stats['mode']}",
                str(resolved_user_id),
            )
            country_rank = await app.state.services.redis.zrevrank(
                f"bancho:leaderboard:{mode_stats['mode']}:{resolved_country}",
                str(resolved_user_id),
            )

            # NOTE: this dict-like return is intentional.
            #       but quite cursed.
            stats_key = str(mode_stats["mode"])
            api_data["stats"][stats_key] = {
                "id": mode_stats["id"],
                "mode": mode_stats["mode"],
                "tscore": mode_stats["tscore"],
                "rscore": mode_stats["rscore"],
                "pp": mode_stats["pp"],
                "plays": mode_stats["plays"],
                "playtime": mode_stats["playtime"],
                "acc": mode_stats["acc"],
                "max_combo": mode_stats["max_combo"],
                "total_hits": mode_stats["total_hits"],
                "replay_views": mode_stats["replay_views"],
                "xh_count": mode_stats["xh_count"],
                "x_count": mode_stats["x_count"],
                "sh_count": mode_stats["sh_count"],
                "s_count": mode_stats["s_count"],
                "a_count": mode_stats["a_count"],
                # extra fields are added to the api response
                "rank": rank + 1 if rank is not None else 0,
                "country_rank": country_rank + 1 if country_rank is not None else 0,
            }

    return ORJSONResponse({"status": "success", "player": api_data})


@router.get("/get_player_status")
async def api_get_player_status(
    user_id: int | None = Query(None, alias="id", ge=3, le=2_147_483_647),
    username: str | None = Query(None, alias="name", pattern=regexes.USERNAME.pattern),
) -> Response:
    """Return a players current status, if they are online."""
    if username and user_id:
        return ORJSONResponse(
            {"status": "Must provide either id OR name!"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if username:
        player = app.state.sessions.players.get(name=username)
    elif user_id:
        player = app.state.sessions.players.get(id=user_id)
    else:
        return ORJSONResponse(
            {"status": "Must provide either id OR name!"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if not player:
        # no such player online, return their last seen time if they exist in sql

        if username:
            row = await users_repo.fetch_one(name=username)
        else:  # if userid
            row = await users_repo.fetch_one(id=user_id)

        if not row:
            return ORJSONResponse(
                {"status": "Player not found."},
                status_code=status.HTTP_404_NOT_FOUND,
            )

        return ORJSONResponse(
            {
                "status": "success",
                "player_status": {
                    "online": False,
                    "last_seen": row["latest_activity"],
                },
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


@router.get("/get_player_scores")
async def api_get_player_scores(
    scope: Literal["recent", "best"],
    user_id: int | None = Query(None, alias="id", ge=3, le=2_147_483_647),
    username: str | None = Query(None, alias="name", pattern=regexes.USERNAME.pattern),
    mods_arg: str | None = Query(None, alias="mods"),
    mode_arg: int = Query(0, alias="mode", ge=0, le=11),
    limit: int = Query(25, ge=1, le=100),
    include_loved: bool = False,
    include_failed: bool = True,
) -> Response:
    """Return a list of a given user's recent/best scores."""
    if mode_arg in (
        GameMode.RELAX_MANIA,
        GameMode.AUTOPILOT_CATCH,
        GameMode.AUTOPILOT_TAIKO,
        GameMode.AUTOPILOT_MANIA,
    ):
        return ORJSONResponse(
            {"status": "Invalid gamemode."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if username and user_id:
        return ORJSONResponse(
            {"status": "Must provide either id OR name!"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if username:
        player = await app.state.sessions.players.from_cache_or_sql(name=username)
    elif user_id:
        player = await app.state.sessions.players.from_cache_or_sql(id=user_id)
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

    # parse args (scope, mode, mods, limit)

    mode = GameMode(mode_arg)

    strong_equality = True
    if mods_arg is not None:
        if mods_arg[0] in ("~", "="):  # weak/strong equality
            strong_equality = mods_arg[0] == "="
            mods_arg = mods_arg[1:]

        if mods_arg.isdecimal():
            # parse from int form
            mods = Mods(int(mods_arg))
        else:
            # parse from string form
            mods = Mods.from_modstr(mods_arg)
    else:
        mods = None

    # build sql query & fetch info

    query = [
        "SELECT t.id, t.map_md5, t.score, t.pp, t.acc, t.max_combo, "
        "t.mods, t.n300, t.n100, t.n50, t.nmiss, t.ngeki, t.nkatu, t.grade, "
        "t.status, t.mode, t.play_time, t.time_elapsed, t.perfect "
        "FROM scores t "
        "INNER JOIN maps b ON t.map_md5 = b.md5 "
        "WHERE t.userid = :user_id AND t.mode = :mode",
    ]

    params: dict[str, object] = {
        "user_id": player.id,
        "mode": mode,
    }

    if mods is not None:
        if strong_equality:
            query.append("AND t.mods & :mods = :mods")
        else:
            query.append("AND t.mods & :mods != 0")

        params["mods"] = mods

    if scope == "best":
        allowed_statuses = [2, 3]

        if include_loved:
            allowed_statuses.append(5)

        query.append("AND t.status = 2 AND b.status IN :statuses")
        params["statuses"] = allowed_statuses
        sort = "t.pp"
    else:
        if not include_failed:
            query.append("AND t.status != 0")

        sort = "t.play_time"

    query.append(f"ORDER BY {sort} DESC LIMIT :limit")
    params["limit"] = limit

    rows = [
        dict(row)
        for row in await app.state.services.database.fetch_all(" ".join(query), params)
    ]

    # fetch & return info from sql
    for row in rows:
        bmap = await Beatmap.from_md5(row.pop("map_md5"))
        row["beatmap"] = bmap.as_dict if bmap else None

    clan: clans_repo.Clan | None = None
    if player.clan_id:
        clan = await clans_repo.fetch_one(id=player.clan_id)

    player_info = {
        "id": player.id,
        "name": player.name,
        "clan": (
            {
                "id": clan["id"],
                "name": clan["name"],
                "tag": clan["tag"],
            }
            if clan is not None
            else None
        ),
    }

    return ORJSONResponse(
        {
            "status": "success",
            "scores": rows,
            "player": player_info,
        },
    )


@router.get("/get_player_most_played")
async def api_get_player_most_played(
    user_id: int | None = Query(None, alias="id", ge=3, le=2_147_483_647),
    username: str | None = Query(None, alias="name", pattern=regexes.USERNAME.pattern),
    mode_arg: int = Query(0, alias="mode", ge=0, le=11),
    limit: int = Query(25, ge=1, le=100),
) -> Response:
    """Return the most played beatmaps of a given player."""
    # NOTE: this will almost certainly not scale well, lol.
    if mode_arg in (
        GameMode.RELAX_MANIA,
        GameMode.AUTOPILOT_CATCH,
        GameMode.AUTOPILOT_TAIKO,
        GameMode.AUTOPILOT_MANIA,
    ):
        return ORJSONResponse(
            {"status": "Invalid gamemode."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if user_id is not None:
        player = await app.state.sessions.players.from_cache_or_sql(id=user_id)
    elif username is not None:
        player = await app.state.sessions.players.from_cache_or_sql(name=username)
    else:
        return ORJSONResponse(
            {"status": "Must provide either id or name."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if not player:
        return ORJSONResponse(
            {"status": "Player not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # parse args (mode, limit)

    mode = GameMode(mode_arg)

    # fetch & return info from sql
    rows = await app.state.services.database.fetch_all(
        "SELECT m.md5, m.id, m.set_id, m.status, "
        "m.artist, m.title, m.version, m.creator, COUNT(*) plays "
        "FROM scores s "
        "INNER JOIN maps m ON m.md5 = s.map_md5 "
        "WHERE s.userid = :user_id "
        "AND s.mode = :mode "
        "GROUP BY s.map_md5 "
        "ORDER BY plays DESC "
        "LIMIT :limit",
        {"user_id": player.id, "mode": mode, "limit": limit},
    )

    return ORJSONResponse(
        {
            "status": "success",
            "maps": [dict(row) for row in rows],
        },
    )


@router.get("/get_map_info")
async def api_get_map_info(
    map_id: int | None = Query(None, alias="id", ge=3, le=2_147_483_647),
    md5: str | None = Query(None, alias="md5", min_length=32, max_length=32),
) -> Response:
    """Return information about a given beatmap."""
    if map_id is not None:
        bmap = await Beatmap.from_bid(map_id)
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

    return ORJSONResponse(
        {
            "status": "success",
            "map": bmap.as_dict,
        },
    )


@router.get("/get_map_scores")
async def api_get_map_scores(
    scope: Literal["recent", "best"],
    map_id: int | None = Query(None, alias="id", ge=0, le=2_147_483_647),
    map_md5: str | None = Query(None, alias="md5", min_length=32, max_length=32),
    mods_arg: str | None = Query(None, alias="mods"),
    mode_arg: int = Query(0, alias="mode", ge=0, le=11),
    limit: int = Query(50, ge=1, le=100),
) -> Response:
    """Return the top n scores on a given beatmap."""
    if mode_arg in (
        GameMode.RELAX_MANIA,
        GameMode.AUTOPILOT_CATCH,
        GameMode.AUTOPILOT_TAIKO,
        GameMode.AUTOPILOT_MANIA,
    ):
        return ORJSONResponse(
            {"status": "Invalid gamemode."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if map_id is not None:
        bmap = await Beatmap.from_bid(map_id)
    elif map_md5 is not None:
        bmap = await Beatmap.from_md5(map_md5)
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

    mode = GameMode(mode_arg)

    strong_equality = True
    if mods_arg is not None:
        if mods_arg[0] in ("~", "="):
            strong_equality = mods_arg[0] == "="
            mods_arg = mods_arg[1:]

        if mods_arg.isdecimal():
            # parse from int form
            mods = Mods(int(mods_arg))
        else:
            # parse from string form
            mods = Mods.from_modstr(mods_arg)
    else:
        mods = None

    # NOTE: userid will eventually become player_id,
    # along with everywhere else in the codebase.
    query = [
        "SELECT s.map_md5, s.score, s.pp, s.acc, s.max_combo, s.mods, "
        "s.n300, s.n100, s.n50, s.nmiss, s.ngeki, s.nkatu, s.grade, s.status, "
        "s.mode, s.play_time, s.time_elapsed, s.userid, s.perfect, "
        "u.name player_name, "
        "c.id clan_id, c.name clan_name, c.tag clan_tag "
        "FROM scores s "
        "INNER JOIN users u ON u.id = s.userid "
        "LEFT JOIN clans c ON c.id = u.clan_id "
        "WHERE s.map_md5 = :map_md5 "
        "AND s.mode = :mode "
        "AND s.status = 2 "
        "AND u.priv & 1",
    ]
    params: dict[str, object] = {
        "map_md5": bmap.md5,
        "mode": mode,
    }

    if mods is not None:
        if strong_equality:
            query.append("AND mods & :mods = :mods")
        else:
            query.append("AND mods & :mods != 0")

        params["mods"] = mods

    # unlike /get_player_scores, we'll sort by score/pp depending
    # on the mode played, since we want to replicated leaderboards.
    if scope == "best":
        sort = "pp" if mode >= GameMode.RELAX_OSU else "score"
    else:  # recent
        sort = "play_time"

    query.append(f"ORDER BY {sort} DESC LIMIT :limit")
    params["limit"] = limit

    rows = await app.state.services.database.fetch_all(" ".join(query), params)

    return ORJSONResponse(
        {
            "status": "success",
            "scores": [dict(row) for row in rows],
        },
    )


@router.get("/get_score_info")
async def api_get_score_info(
    score_id: int = Query(..., alias="id", ge=0, le=9_223_372_036_854_775_807),
) -> Response:
    """Return information about a given score."""
    score = await scores_repo.fetch_one(score_id)

    if score is None:
        return ORJSONResponse(
            {"status": "Score not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return ORJSONResponse({"status": "success", "score": score})


@router.get("/get_replay")
async def api_get_replay(
    score_id: int = Query(..., alias="id", ge=0, le=9_223_372_036_854_775_807),
    include_headers: bool = True,
) -> Response:
    """\
    Return a given replay (including headers).

    Note that this endpoint does not increment
    the player's total replay views.
    """
    # fetch replay file & make sure it exists
    replay_file = REPLAYS_PATH / f"{score_id}.osr"
    if not replay_file.exists():
        return ORJSONResponse(
            {"status": "Replay not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )
    # read replay frames from file
    raw_replay_data = replay_file.read_bytes()
    if not include_headers:
        return Response(
            bytes(raw_replay_data),
            media_type="application/octet-stream",
            headers={
                "Content-Description": "File Transfer",
                # TODO: should we include a Content-Disposition?
            },
        )
    # add replay headers from sql
    # TODO: osu_version & life graph in scores tables?
    row = await app.state.services.database.fetch_one(
        "SELECT u.name username, m.md5 map_md5, "
        "m.artist, m.title, m.version, "
        "s.mode, s.n300, s.n100, s.n50, s.ngeki, "
        "s.nkatu, s.nmiss, s.score, s.max_combo, "
        "s.perfect, s.mods, s.play_time "
        "FROM scores s "
        "INNER JOIN users u ON u.id = s.userid "
        "INNER JOIN maps m ON m.md5 = s.map_md5 "
        "WHERE s.id = :score_id",
        {"score_id": score_id},
    )
    if not row:
        # score not found in sql
        return ORJSONResponse(
            {"status": "Score not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )  # but replay was?
    # generate the replay's hash
    replay_md5 = hashlib.md5(
        "{}p{}o{}o{}t{}a{}r{}e{}y{}o{}u{}{}{}".format(
            row["n100"] + row["n300"],
            row["n50"],
            row["ngeki"],
            row["nkatu"],
            row["nmiss"],
            row["map_md5"],
            row["max_combo"],
            str(row["perfect"] == 1),
            row["username"],
            row["score"],
            0,  # TODO: rank
            row["mods"],
            "True",  # TODO: ??
        ).encode(),
    ).hexdigest()
    # create a buffer to construct the replay output
    replay_data = bytearray()
    # pack first section of headers.
    replay_data += struct.pack(
        "<Bi",
        GameMode(row["mode"]).as_vanilla,
        20200207,
    )  # TODO: osuver
    replay_data += app.packets.write_string(row["map_md5"])
    replay_data += app.packets.write_string(row["username"])
    replay_data += app.packets.write_string(replay_md5)
    replay_data += struct.pack(
        "<hhhhhhihBi",
        row["n300"],
        row["n100"],
        row["n50"],
        row["ngeki"],
        row["nkatu"],
        row["nmiss"],
        row["score"],
        row["max_combo"],
        row["perfect"],
        row["mods"],
    )
    replay_data += b"\x00"  # TODO: hp graph
    timestamp = int(row["play_time"].timestamp() * 1e7)
    replay_data += struct.pack("<q", timestamp + DATETIME_OFFSET)
    # pack the raw replay data into the buffer
    replay_data += struct.pack("<i", len(raw_replay_data))
    replay_data += raw_replay_data
    # pack additional info buffer.
    replay_data += struct.pack("<q", score_id)
    # NOTE: target practice sends extra mods, but
    # can't submit scores so should not be a problem.
    # stream data back to the client
    return Response(
        bytes(replay_data),
        media_type="application/octet-stream",
        headers={
            "Content-Description": "File Transfer",
            "Content-Disposition": (
                'attachment; filename="{username} - '
                "{artist} - {title} [{version}] "
                '({play_time:%Y-%m-%d}).osr"'
            ).format(**dict(row._mapping)),
        },
    )


@router.get("/get_match")
async def api_get_match(
    match_id: int = Query(..., alias="id", ge=1, le=64),
) -> Response:
    """Return information of a given multiplayer match."""
    match = app.state.sessions.matches[match_id]
    if not match:
        return ORJSONResponse(
            {"status": "Match not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return ORJSONResponse(
        {
            "status": "success",
            "match": {
                "name": match.name,
                "mode": match.mode,
                "mods": int(match.mods),
                "seed": match.seed,
                "host": {"id": match.host.id, "name": match.host.name},
                "refs": [
                    {"id": player.id, "name": player.name} for player in match.refs
                ],
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


@router.get("/get_leaderboard")
async def api_get_global_leaderboard(
    sort: Literal["tscore", "rscore", "pp", "acc", "plays", "playtime"] = "pp",
    mode_arg: int = Query(0, alias="mode", ge=0, le=11),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, min=0, max=2_147_483_647),
    country: str | None = Query(None, min_length=2, max_length=2),
) -> Response:
    if mode_arg in (
        GameMode.RELAX_MANIA,
        GameMode.AUTOPILOT_CATCH,
        GameMode.AUTOPILOT_TAIKO,
        GameMode.AUTOPILOT_MANIA,
    ):
        return ORJSONResponse(
            {"status": "Invalid gamemode."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    mode = GameMode(mode_arg)

    query_conditions = ["s.mode = :mode", "u.priv & 1", f"s.{sort} > 0"]
    query_parameters: dict[str, object] = {"mode": mode}

    if country is not None:
        query_conditions.append("u.country = :country")
        query_parameters["country"] = country

    rows = await app.state.services.database.fetch_all(
        "SELECT u.id as player_id, u.name, u.country, s.tscore, s.rscore, "
        "s.pp, s.plays, s.playtime, s.acc, s.max_combo, "
        "s.xh_count, s.x_count, s.sh_count, s.s_count, s.a_count, "
        "c.id as clan_id, c.name as clan_name, c.tag as clan_tag "
        "FROM stats s "
        "LEFT JOIN users u USING (id) "
        "LEFT JOIN clans c ON u.clan_id = c.id "
        f"WHERE {' AND '.join(query_conditions)} "
        f"ORDER BY s.{sort} DESC LIMIT :offset, :limit",
        query_parameters | {"offset": offset, "limit": limit},
    )

    return ORJSONResponse(
        {"status": "success", "leaderboard": [dict(row) for row in rows]},
    )


@router.get("/get_clan")
async def api_get_clan(
    clan_id: int = Query(..., alias="id", ge=1, le=2_147_483_647),
) -> Response:
    """Return information of a given clan."""
    clan = await clans_repo.fetch_one(id=clan_id)
    if not clan:
        return ORJSONResponse(
            {"status": "Clan not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    clan_members = await users_repo.fetch_many(clan_id=clan["id"])

    owner = await app.state.sessions.players.from_cache_or_sql(id=clan["owner"])
    assert owner is not None

    return ORJSONResponse(
        {
            "id": clan["id"],
            "name": clan["name"],
            "tag": clan["tag"],
            "members": [
                {
                    "id": member["id"],
                    "name": member["name"],
                    "country": member["country"],
                    "rank": ("Member", "Officer", "Owner")[member["clan_priv"] - 1],
                }
                for member in clan_members
            ],
            "owner": {
                "id": owner.id,
                "name": owner.name,
                "country": owner.geoloc["country"]["acronym"],
                "rank": "Owner",
            },
        },
    )


@router.get("/get_mappool")
async def api_get_pool(
    pool_id: int = Query(..., alias="id", ge=1, le=2_147_483_647),
) -> Response:
    """Return information of a given mappool."""

    tourney_pool = await tourney_pools_repo.fetch_by_id(id=pool_id)
    if tourney_pool is None:
        return ORJSONResponse(
            {"status": "Pool not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    tourney_pool_maps: dict[tuple[int, int], Beatmap] = {}
    for pool_map in await tourney_pool_maps_repo.fetch_many(pool_id=pool_id):
        bmap = await Beatmap.from_bid(pool_map["map_id"])
        if bmap is not None:
            tourney_pool_maps[(pool_map["mods"], pool_map["slot"])] = bmap

    pool_creator = app.state.sessions.players.get(id=tourney_pool["created_by"])

    if pool_creator is None:
        return ORJSONResponse(
            {"status": "Pool creator not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    pool_creator_clan = await clans_repo.fetch_one(id=pool_creator.clan_id)
    pool_creator_clan_members: list[users_repo.User] = []
    if pool_creator_clan is not None:
        pool_creator_clan_members = await users_repo.fetch_many(
            clan_id=pool_creator.clan_id,
        )

    return ORJSONResponse(
        {
            "id": tourney_pool["id"],
            "name": tourney_pool["name"],
            "created_at": tourney_pool["created_at"],
            "created_by": {
                "id": pool_creator.id,
                "name": pool_creator.name,
                "country": pool_creator.geoloc["country"]["acronym"],
                "clan": (
                    {
                        "id": pool_creator_clan["id"],
                        "name": pool_creator_clan["name"],
                        "tag": pool_creator_clan["tag"],
                        "members": len(pool_creator_clan_members),
                    }
                    if pool_creator_clan is not None
                    else None
                ),
                "online": pool_creator.is_online,
            },
            "maps": {
                f"{mods!r}{slot}": {
                    "id": bmap.id,
                    "md5": bmap.md5,
                    "set_id": bmap.set_id,
                    "artist": bmap.artist,
                    "title": bmap.title,
                    "version": bmap.version,
                    "creator": bmap.creator,
                    "last_update": bmap.last_update,
                    "total_length": bmap.total_length,
                    "max_combo": bmap.max_combo,
                    "status": bmap.status,
                    "plays": bmap.plays,
                    "passes": bmap.passes,
                    "mode": bmap.mode,
                    "bpm": bmap.bpm,
                    "cs": bmap.cs,
                    "od": bmap.od,
                    "ar": bmap.ar,
                    "hp": bmap.hp,
                    "diff": bmap.diff,
                }
                for (mods, slot), bmap in tourney_pool_maps.items()
            },
        },
    )


# def requires_api_key(f: Callable) -> Callable:
#     @wraps(f)
#     async def wrapper(conn: Connection) -> HTTPResponse:
#         conn.resp_headers["Content-Type"] = "application/json"
#         if "Authorization" not in conn.headers:
#             return (400, JSON({"status": "Must provide authorization token."}))

#         api_key = conn.headers["Authorization"]

#         if api_key not in app.state.sessions.api_keys:
#             return (401, JSON({"status": "Unknown authorization token."}))

#         # get player from api token
#         player_id = app.state.sessions.api_keys[api_key]
#         player = await app.state.sessions.players.from_cache_or_sql(id=player_id)

#         return await f(conn, player)

#     return wrapper


# NOTE: `Content-Type = application/json` is applied in the above decorator
#                                         for the following api handlers.


# @domain.route("/set_avatar", methods=["POST", "PUT"])
# @requires_api_key
# async def api_set_avatar(conn: Connection, player: Player) -> HTTPResponse:
#     """Update the tokenholder's avatar to a given file."""
#     if "avatar" not in conn.files:
#         return (400, JSON({"status": "must provide avatar file."}))

#     ava_file = conn.files["avatar"]

#     # block files over 4MB
#     if len(ava_file) > (4 * 1024 * 1024):
#         return (400, JSON({"status": "avatar file too large (max 4MB)."}))

#     if ava_file[6:10] in (b"JFIF", b"Exif"):
#         ext = "jpeg"
#     elif ava_file.startswith(b"\211PNG\r\n\032\n"):
#         ext = "png"
#     else:
#         return (400, JSON({"status": "invalid file type."}))

#     # write to the avatar file
#     (AVATARS_PATH / f"{player.id}.{ext}").write_bytes(ava_file)
#     return JSON({"status": "success."})
