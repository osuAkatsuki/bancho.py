"""api: bancho.py's developer api for interacting with server state"""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path as SystemPath
from typing import Annotated
from typing import Literal
from typing import cast

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
from app.api import dependencies as api_dependencies
from app.constants import regexes
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.objects.beatmap import Beatmap
from app.objects.beatmap import ensure_osu_file_is_available
from app.repositories.users import User
from app.services.clans import ClansService
from app.services.performance import PerformanceService
from app.services.performance import ScoreParams
from app.services.players import PlayersService
from app.services.scores import ScoresService
from app.services.tourney_pools import TourneyPoolsService

AVATARS_PATH = SystemPath.cwd() / ".data/avatars"
BEATMAPS_PATH = SystemPath.cwd() / ".data/osu"
REPLAYS_PATH = SystemPath.cwd() / ".data/osr"
SCREENSHOTS_PATH = SystemPath.cwd() / ".data/ss"


router = APIRouter()
http_bearer_scheme = HTTPBearer(auto_error=False)

# NOTE: The V1 APIs should not be used if a V2 API is available.
#       These APIs may be deprecated in the future.

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
# GET /calculate_pp: calculate & return pp for a given beatmap.

DATETIME_OFFSET = 0x89F7FF5F7B58000


@router.get("/calculate_pp")
async def api_calculate_pp(
    *,
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
    token: HTTPCredentials | None = Depends(http_bearer_scheme),
    performance_service: Annotated[
        PerformanceService,
        Depends(api_dependencies.get_performance_service),
    ],
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

    results = performance_service.calculate_performances(
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
    *,
    search: str | None = Query(None, alias="q", min=2, max=32),
    players_service: Annotated[
        PlayersService,
        Depends(api_dependencies.get_players_service),
    ],
) -> Response:
    """Search for users on the server by name."""
    rows = await players_service.search_public_players(search)

    return ORJSONResponse(
        {
            "status": "success",
            "results": len(rows),
            "result": rows,
        },
    )


@router.get("/get_player_count")
async def api_get_player_count(
    players_service: Annotated[
        PlayersService,
        Depends(api_dependencies.get_players_service),
    ],
) -> Response:
    """Get the current amount of online players."""
    return ORJSONResponse(
        {
            "status": "success",
            "counts": {
                # -1 for the bot, who is always online
                "online": players_service.fetch_online_player_count(),
                "total": await players_service.fetch_total_player_count(),
            },
        },
    )


@router.get("/get_player_info")
async def api_get_player_info(
    scope: Literal["stats", "info", "all"],
    *,
    user_id: int | None = Query(None, alias="id", ge=3, le=2_147_483_647),
    username: str | None = Query(None, alias="name", pattern=regexes.USERNAME.pattern),
    players_service: Annotated[
        PlayersService,
        Depends(api_dependencies.get_players_service),
    ],
) -> Response:
    """Return information about a given player."""
    if not (username or user_id) or (username and user_id):
        return ORJSONResponse(
            {"status": "Must provide either id OR name!"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user_info = await players_service.fetch_player_by_id_or_name(
        user_id=user_id,
        username=username,
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
        api_data["info"] = dict(user_info)

    # fetch user's stats if requested
    if scope in ("stats", "all"):
        api_data["stats"] = {}

        # get all stats
        all_stats = await players_service.fetch_all_player_stats(resolved_user_id)

        for mode_stats in all_stats:
            rank = cast(
                int | None,
                await app.state.services.redis.zrevrank(
                    f"bancho:leaderboard:{mode_stats['mode']}",
                    str(resolved_user_id),
                ),
            )
            country_rank = cast(
                int | None,
                await app.state.services.redis.zrevrank(
                    f"bancho:leaderboard:{mode_stats['mode']}:{resolved_country}",
                    str(resolved_user_id),
                ),
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
    *,
    user_id: int | None = Query(None, alias="id", ge=3, le=2_147_483_647),
    username: str | None = Query(None, alias="name", pattern=regexes.USERNAME.pattern),
    players_service: Annotated[
        PlayersService,
        Depends(api_dependencies.get_players_service),
    ],
) -> Response:
    """Return a players current status, if they are online."""
    if username and user_id:
        return ORJSONResponse(
            {"status": "Must provide either id OR name!"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if username is None and user_id is None:
        return ORJSONResponse(
            {"status": "Must provide either id OR name!"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    player = players_service.fetch_online_player(
        user_id=user_id,
        username=username,
    )

    if not player:
        # no such player online, return their last seen time if they exist in sql

        row = await players_service.fetch_player_by_id_or_name(
            user_id=user_id,
            username=username,
        )

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
    *,
    user_id: int | None = Query(None, alias="id", ge=3, le=2_147_483_647),
    username: str | None = Query(None, alias="name", pattern=regexes.USERNAME.pattern),
    mods_arg: str | None = Query(None, alias="mods"),
    mode_arg: int = Query(0, alias="mode", ge=0, le=11),
    limit: int = Query(25, ge=1, le=100),
    include_loved: bool = False,
    include_failed: bool = True,
    players_service: Annotated[
        PlayersService,
        Depends(api_dependencies.get_players_service),
    ],
    scores_service: Annotated[
        ScoresService,
        Depends(api_dependencies.get_scores_service),
    ],
    clans_service: Annotated[
        ClansService,
        Depends(api_dependencies.get_clans_service),
    ],
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

    if username is None and user_id is None:
        return ORJSONResponse(
            {"status": "Must provide either id OR name!"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    player = await players_service.fetch_player_session(
        user_id=user_id,
        username=username,
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

    rows = await scores_service.fetch_player_scores(
        player_id=player.id,
        mode=mode,
        mods=mods,
        strong_mods_equality=strong_equality,
        scope=scope,
        limit=limit,
        include_loved=include_loved,
        include_failed=include_failed,
    )

    clan = None
    if player.clan_id:
        clan = await clans_service.fetch_clan(player.clan_id)

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
    *,
    user_id: int | None = Query(None, alias="id", ge=3, le=2_147_483_647),
    username: str | None = Query(None, alias="name", pattern=regexes.USERNAME.pattern),
    mode_arg: int = Query(0, alias="mode", ge=0, le=11),
    limit: int = Query(25, ge=1, le=100),
    players_service: Annotated[
        PlayersService,
        Depends(api_dependencies.get_players_service),
    ],
    scores_service: Annotated[
        ScoresService,
        Depends(api_dependencies.get_scores_service),
    ],
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

    if user_id is None and username is None:
        return ORJSONResponse(
            {"status": "Must provide either id or name."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    player = await players_service.fetch_player_session(
        user_id=user_id,
        username=username,
    )

    if not player:
        return ORJSONResponse(
            {"status": "Player not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # parse args (mode, limit)

    mode = GameMode(mode_arg)

    rows = await scores_service.fetch_player_most_played(
        player_id=player.id,
        mode=mode,
        limit=limit,
    )

    return ORJSONResponse(
        {
            "status": "success",
            "maps": rows,
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
    *,
    map_id: int | None = Query(None, alias="id", ge=0, le=2_147_483_647),
    map_md5: str | None = Query(None, alias="md5", min_length=32, max_length=32),
    mods_arg: str | None = Query(None, alias="mods"),
    mode_arg: int = Query(0, alias="mode", ge=0, le=11),
    limit: int = Query(50, ge=1, le=100),
    scores_service: Annotated[
        ScoresService,
        Depends(api_dependencies.get_scores_service),
    ],
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

    rows = await scores_service.fetch_map_scores(
        map_md5=bmap.md5,
        mode=mode,
        mods=mods,
        strong_mods_equality=strong_equality,
        scope=scope,
        limit=limit,
    )

    return ORJSONResponse(
        {
            "status": "success",
            "scores": rows,
        },
    )


@router.get("/get_score_info")
async def api_get_score_info(
    *,
    score_id: int = Query(..., alias="id", ge=0, le=9_223_372_036_854_775_807),
    scores_service: Annotated[
        ScoresService,
        Depends(api_dependencies.get_scores_service),
    ],
) -> Response:
    """Return information about a given score."""
    score = await scores_service.fetch_score(score_id)

    if score is None:
        return ORJSONResponse(
            {"status": "Score not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return ORJSONResponse({"status": "success", "score": score})


@router.get("/get_replay")
async def api_get_replay(
    *,
    score_id: int = Query(..., alias="id", ge=0, le=9_223_372_036_854_775_807),
    include_headers: bool = True,
    scores_service: Annotated[
        ScoresService,
        Depends(api_dependencies.get_scores_service),
    ],
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
    row = await scores_service.fetch_replay_header(score_id)
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
            ).format(**row),
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
    *,
    sort: Literal["tscore", "rscore", "pp", "acc", "plays", "playtime"] = "pp",
    mode_arg: int = Query(0, alias="mode", ge=0, le=11),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, min=0, max=2_147_483_647),
    country: str | None = Query(None, min_length=2, max_length=2),
    players_service: Annotated[
        PlayersService,
        Depends(api_dependencies.get_players_service),
    ],
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

    rows = await players_service.fetch_global_leaderboard(
        sort=sort,
        mode=mode,
        limit=limit,
        offset=offset,
        country=country,
    )

    return ORJSONResponse(
        {"status": "success", "leaderboard": rows},
    )


@router.get("/get_clan")
async def api_get_clan(
    *,
    clan_id: int = Query(..., alias="id", ge=1, le=2_147_483_647),
    clans_service: Annotated[
        ClansService,
        Depends(api_dependencies.get_clans_service),
    ],
    players_service: Annotated[
        PlayersService,
        Depends(api_dependencies.get_players_service),
    ],
) -> Response:
    """Return information of a given clan."""
    clan = await clans_service.fetch_clan(clan_id)
    if not clan:
        return ORJSONResponse(
            {"status": "Clan not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    clan_members = await clans_service.fetch_clan_members(clan["id"])

    owner = await players_service.fetch_player_session(
        user_id=clan["owner"],
        username=None,
    )
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
    *,
    pool_id: int = Query(..., alias="id", ge=1, le=2_147_483_647),
    tourney_pools_service: Annotated[
        TourneyPoolsService,
        Depends(api_dependencies.get_tourney_pools_service),
    ],
    players_service: Annotated[
        PlayersService,
        Depends(api_dependencies.get_players_service),
    ],
    clans_service: Annotated[
        ClansService,
        Depends(api_dependencies.get_clans_service),
    ],
) -> Response:
    """Return information of a given mappool."""

    tourney_pool = await tourney_pools_service.fetch_tourney_pool(pool_id)
    if tourney_pool is None:
        return ORJSONResponse(
            {"status": "Pool not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    tourney_pool_maps: dict[tuple[int, int], Beatmap] = {}
    for pool_map in await tourney_pools_service.fetch_tourney_pool_maps(pool_id):
        bmap = await Beatmap.from_bid(pool_map["map_id"])
        if bmap is not None:
            tourney_pool_maps[(pool_map["mods"], pool_map["slot"])] = bmap

    pool_creator = players_service.fetch_online_player(
        user_id=tourney_pool["created_by"],
        username=None,
    )

    if pool_creator is None:
        return ORJSONResponse(
            {"status": "Pool creator not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    pool_creator_clan = (
        await clans_service.fetch_clan(pool_creator.clan_id)
        if pool_creator.clan_id is not None
        else None
    )
    pool_creator_clan_members: list[User] = []
    if pool_creator_clan is not None:
        assert pool_creator.clan_id is not None
        pool_creator_clan_members = await clans_service.fetch_clan_members(
            pool_creator.clan_id,
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
