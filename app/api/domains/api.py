""" api: gulag's public api for developers """
import hashlib
import struct
from pathlib import Path as SystemPath
from typing import Literal
from typing import Optional

from fastapi import APIRouter
from fastapi import status
from fastapi.param_functions import Query
from fastapi.responses import ORJSONResponse
from fastapi.responses import StreamingResponse

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


@router.get("/api/get_player_count")
async def api_get_player_count():
    """Get the current amount of online players."""
    # TODO: perhaps add peak(s)? (24h, 5d, 3w, etc.)
    # NOTE: -1 is for the bot, and will have to change
    # if we ever make some sort of bot creation system.
    total_users = await app.services.database.fetch_val(
        "SELECT COUNT(*) FROM users",
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
):
    """Return information about a given player."""
    if not (username or user_id) or (username and user_id):
        return ORJSONResponse(
            {"status": "Must provide either id OR name!"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # get user info from username or user id
    if username:
        user_info = await app.services.database.fetch_one(
            "SELECT id, name, safe_name, "
            "priv, country, silence_end "
            "FROM users WHERE safe_name = :username",
            {"username": username.lower()},
        )
    else:  # if user_id
        user_info = await app.services.database.fetch_one(
            "SELECT id, name, safe_name, "
            "priv, country, silence_end "
            "FROM users WHERE id = :userid",
            {"userid": user_id},
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
        rows = await app.services.database.fetch_all(
            "SELECT tscore, rscore, pp, plays, playtime, acc, max_combo, "
            "xh_count, x_count, sh_count, s_count, a_count FROM stats "
            "WHERE id = :userid",
            {"userid": resolved_user_id},
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
):
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
            row = await app.services.database.fetch_one(
                "SELECT latest_activity FROM users WHERE id = :id",
                {"id": username},
            )
        else:  # if user_id
            row = await app.services.database.fetch_one(
                "SELECT latest_activity FROM users WHERE id = :id",
                {"id": user_id},
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
):
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

    if (mode_arg := conn.args.get("mode", None)) is not None:
        if not (mode_arg.isdecimal() and 0 <= (mode := int(mode_arg)) <= 7):
            return ORJSONResponse(
                {"status": "Invalid mode."},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        mode = GameMode(mode)
    else:
        mode = GameMode.VANILLA_OSU

    if (mods_arg := conn.args.get("mods", None)) is not None:
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

    if (limit_arg := conn.args.get("limit", None)) is not None:
        if not (limit_arg.isdecimal() and 0 < (limit := int(limit_arg)) <= 100):
            return ORJSONResponse(
                {"status": "Invalid limit."},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
    else:
        limit = 25

    # build sql query & fetch info

    query = [
        "SELECT t.id, t.map_md5, t.score, t.pp, t.acc, t.max_combo, "
        "t.mods, t.n300, t.n100, t.n50, t.nmiss, t.ngeki, t.nkatu, t.grade, "
        "t.status, t.mode, t.play_time, t.time_elapsed, t.perfect "
        f"FROM {mode.scores_table} t "
        "INNER JOIN maps b ON t.map_md5 = b.md5 "
        "WHERE t.userid = %s AND t.mode = %s",
    ]

    params = [player.id, mode.as_vanilla]

    if mods is not None:
        if strong_equality:
            query.append("AND t.mods & %s = %s")
            params.extend((mods, mods))
        else:
            query.append("AND t.mods & %s != 0")
            params.append(mods)

    if scope == "best":
        include_loved = (
            "include_loved" in conn.args and conn.args["include_loved"] == "1"
        )

        allowed_statuses = [2, 3]

        if include_loved:
            allowed_statuses.append(5)

        query.append("AND t.status = 2 AND b.status IN %s")
        params.append(allowed_statuses)
        sort = "t.pp"
    else:
        sort = "t.play_time"

    query.append(f"ORDER BY {sort} DESC LIMIT %s")
    params.append(limit)

    # fetch & return info from sql
    res = await app.services.database.fetch_all(" ".join(query), params)

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
async def api_get_player_most_played():
    """Return the most played beatmaps of a given player."""
    # NOTE: this will almost certainly not scale well, lol.
    conn.resp_headers["Content-Type"] = "application/json"

    if "id" in conn.args:
        if not conn.args["id"].isdecimal():
            return ORJSONResponse(
                {"status": "Invalid player id."},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        p = await glob.players.from_cache_or_sql(id=int(conn.args["id"]))
    elif "name" in conn.args:
        if not 0 < len(conn.args["name"]) <= 16:
            return ORJSONResponse(
                {"status": "Invalid player name."},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        p = await glob.players.from_cache_or_sql(name=conn.args["name"])
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

    if (mode_arg := conn.args.get("mode", None)) is not None:
        if not (mode_arg.isdecimal() and 0 <= (mode := int(mode_arg)) <= 7):
            return ORJSONResponse(
                {"status": "Invalid mode."},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        mode = GameMode(mode)
    else:
        mode = GameMode.VANILLA_OSU

    if (limit_arg := conn.args.get("limit", None)) is not None:
        if not (limit_arg.isdecimal() and 0 < (limit := int(limit_arg)) <= 100):
            return ORJSONResponse(
                {"status": "Invalid limit."},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
    else:
        limit = 25

    # fetch & return info from sql
    res = await app.services.database.fetch_all(
        "SELECT m.md5, m.id, m.set_id, m.status, "
        "m.artist, m.title, m.version, m.creator, COUNT(*) plays "
        f"FROM {mode.scores_table} s "
        "INNER JOIN maps m ON m.md5 = s.map_md5 "
        "WHERE s.userid = %s "
        "AND s.mode = %s "
        "GROUP BY s.map_md5 "
        "ORDER BY plays DESC "
        "LIMIT %s",
        [p.id, mode.as_vanilla, limit],
    )

    return ORJSONResponse({"status": "success", "maps": res})


@router.get("/api/get_map_info")
async def api_get_map_info():
    """Return information about a given beatmap."""
    conn.resp_headers["Content-Type"] = "application/json"
    if "id" in conn.args:
        if not conn.args["id"].isdecimal():
            return ORJSONResponse(
                {"status": "Invalid map id."},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        bmap = await Beatmap.from_bid(int(conn.args["id"]))
    elif "md5" in conn.args:
        if len(conn.args["md5"]) != 32:
            return ORJSONResponse(
                {"status": "Invalid map md5."},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        bmap = await Beatmap.from_md5(conn.args["md5"])
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
async def api_get_map_scores():
    """Return the top n scores on a given beatmap."""
    conn.resp_headers["Content-Type"] = "application/json"
    if "id" in conn.args:
        if not conn.args["id"].isdecimal():
            return ORJSONResponse(
                {"status": "Invalid map id."},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        bmap = await Beatmap.from_bid(int(conn.args["id"]))
    elif "md5" in conn.args:
        if len(conn.args["md5"]) != 32:
            return ORJSONResponse(
                {"status": "Invalid map md5."},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        bmap = await Beatmap.from_md5(conn.args["md5"])
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

    if "scope" not in conn.args or conn.args["scope"] not in ("recent", "best"):
        return ORJSONResponse(
            {"status": "Must provide valid scope (recent/best)."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    scope = conn.args["scope"]

    if (mode_arg := conn.args.get("mode", None)) is not None:
        if not (mode_arg.isdecimal() and 0 <= (mode := int(mode_arg)) <= 7):
            return ORJSONResponse(
                {"status": "Invalid mode."},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        mode = GameMode(mode)
    else:
        mode = GameMode.VANILLA_OSU

    if (mods_arg := conn.args.get("mods", None)) is not None:
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

    if (limit_arg := conn.args.get("limit", None)) is not None:
        if not (limit_arg.isdecimal() and 0 < (limit := int(limit_arg)) <= 100):
            return ORJSONResponse(
                {"status": "Invalid limit."},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
    else:
        limit = 50

    # NOTE: userid will eventually become player_id,
    # along with everywhere else in the codebase.
    query = [
        "SELECT s.map_md5, s.score, s.pp, s.acc, s.max_combo, s.mods, "
        "s.n300, s.n100, s.n50, s.nmiss, s.ngeki, s.nkatu, s.grade, s.status, "
        "s.mode, s.play_time, s.time_elapsed, s.userid, s.perfect, "
        "u.name player_name, "
        "c.id clan_id, c.name clan_name, c.tag clan_tag "
        f"FROM {mode.scores_table} s "
        "INNER JOIN users u ON u.id = s.userid "
        "LEFT JOIN clans c ON c.id = u.clan_id "
        "WHERE s.map_md5 = %s AND s.mode = %s AND s.status = 2",
    ]
    params = [bmap.md5, mode.as_vanilla]

    if mods is not None:
        if strong_equality:
            query.append("AND mods & %s = %s")
            params.extend((mods, mods))
        else:
            query.append("AND mods & %s != 0")
            params.append(mods)

    # unlike /api/get_player_scores, we'll sort by score/pp depending
    # on the mode played, since we want to replicated leaderboards.
    if scope == "best":
        sort = "pp" if mode >= GameMode.RELAX_OSU else "score"
    else:  # recent
        sort = "play_time"

    query.append(f"ORDER BY {sort} DESC LIMIT %s")
    params.append(limit)

    res = await app.services.database.fetch_all(" ".join(query), params)
    return ORJSONResponse({"status": "success", "scores": res})


@router.get("/api/get_score_info")
async def api_get_score_info():
    """Return information about a given score."""
    conn.resp_headers["Content-Type"] = "application/json"
    if not ("id" in conn.args and conn.args["id"].isdecimal()):
        return ORJSONResponse(
            {"status": "Must provide score id."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    score_id = int(conn.args["id"])

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

    res = await app.services.database.fetch_one(
        "SELECT map_md5, score, pp, acc, max_combo, mods, "
        "n300, n100, n50, nmiss, ngeki, nkatu, grade, status, "
        "mode, play_time, time_elapsed, perfect "
        f"FROM {scores_table} "
        "WHERE id = :score_id",
        {"score_id": score_id},
    )

    if not res:
        return ORJSONResponse(
            {"status": "Score not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return ORJSONResponse({"status": "success", "score": res})


@router.get("/api/get_replay")
async def api_get_replay():
    """Return a given replay (including headers)."""
    conn.resp_headers["Content-Type"] = "application/json"
    if not ("id" in conn.args and conn.args["id"].isdecimal()):
        return ORJSONResponse(
            {"status": "Must provide score id."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    score_id = int(conn.args["id"])

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

    if (
        "include_headers" in conn.args
        and conn.args["include_headers"].lower() == "false"
    ):
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
    res = await app.services.database.fetch_one(
        "SELECT u.name username, m.md5 map_md5, "
        "m.artist, m.title, m.version, "
        "s.mode, s.n300, s.n100, s.n50, s.ngeki, "
        "s.nkatu, s.nmiss, s.score, s.max_combo, "
        "s.perfect, s.mods, s.play_time "
        f"FROM {scores_table} s "
        "INNER JOIN users u ON u.id = s.userid "
        "INNER JOIN maps m ON m.md5 = s.map_md5 "
        "WHERE s.id = :score_id",
        {"score_id": score_id},
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
async def api_get_match():
    """Return information of a given multiplayer match."""
    conn.resp_headers["Content-Type"] = "application/json"
    # TODO: eventually, this should contain recent score info.
    if not (
        "id" in conn.args
        and conn.args["id"].isdecimal()
        and 0 <= (match_id := int(conn.args["id"])) < 64
    ):
        return ORJSONResponse(
            {"status": "Must provide valid match id."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

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
async def api_get_global_leaderboard():
    conn.resp_headers["Content-Type"] = "application/json"

    if (mode_arg := conn.args.get("mode", None)) is not None:
        if not (mode_arg.isdecimal() and 0 <= (mode := int(mode_arg)) <= 7):
            return ORJSONResponse(
                {"status": "Invalid mode."},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        mode = GameMode(mode)
    else:
        mode = GameMode.VANILLA_OSU

    if (limit_arg := conn.args.get("limit", None)) is not None:
        if not (limit_arg.isdecimal() and 0 < (limit := int(limit_arg)) <= 100):
            return ORJSONResponse(
                {"status": "Invalid limit."},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
    else:
        limit = 25

    if (sort := conn.args.get("sort", None)) is not None:
        if sort not in ("tscore", "rscore", "pp", "acc"):
            return ORJSONResponse(
                {"status": "Invalid sort."},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
    else:
        sort = "pp"

    res = await app.services.database.fetch_all(
        "SELECT u.id as player_id, u.name, u.country, s.tscore, s.rscore, "
        "s.pp, s.plays, s.playtime, s.acc, s.max_combo, "
        "s.xh_count, s.x_count, s.sh_count, s.s_count, s.a_count, "
        "c.id as clan_id, c.name as clan_name, c.tag as clan_tag "
        "FROM stats s "
        "LEFT JOIN users u USING (id) "
        "LEFT JOIN clans c ON u.clan_id = c.id "
        f"WHERE s.mode = :mode AND u.priv & 1 AND s.{sort} > 0 "
        f"ORDER BY s.{sort} DESC LIMIT :limit",  # TODO: does this need to be fstring?
        {"mode": mode, "limit": limit},
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
