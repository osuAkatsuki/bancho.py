from __future__ import annotations

from enum import IntEnum
from enum import unique
from typing import Any
from typing import Literal
from urllib.parse import unquote_plus

from fastapi.param_functions import Depends
from fastapi.param_functions import Query
from fastapi.responses import Response
from fastapi.routing import APIRouter

import app.packets
import app.state
import app.utils
from app.api.web.authentication import authenticate_player_session
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.objects.beatmap import Beatmap
from app.objects.beatmap import RankedStatus
from app.objects.player import Player
from app.repositories import clans as clans_repo
from app.repositories import maps as maps_repo
from app.repositories import ratings as ratings_repo
from app.utils import escape_enum
from app.utils import pymysql_encode

SCORE_LISTING_FMTSTR = (
    "{id}|{name}|{score}|{max_combo}|"
    "{n50}|{n100}|{n300}|{nmiss}|{nkatu}|{ngeki}|"
    "{perfect}|{mods}|{userid}|{rank}|{time}|{has_replay}"
)


@unique
@pymysql_encode(escape_enum)
class LeaderboardType(IntEnum):
    Local = 0
    Top = 1
    Mods = 2
    Friends = 3
    Country = 4


router = APIRouter()


async def get_leaderboard_scores(
    leaderboard_type: LeaderboardType | int,
    map_md5: str,
    mode: int,
    mods: Mods,
    player: Player,
    scoring_metric: Literal["pp", "score"],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    query = [
        f"SELECT s.id, s.{scoring_metric} AS _score, "
        "s.max_combo, s.n50, s.n100, s.n300, "
        "s.nmiss, s.nkatu, s.ngeki, s.perfect, s.mods, "
        "UNIX_TIMESTAMP(s.play_time) time, u.id userid, "
        "COALESCE(CONCAT('[', c.tag, '] ', u.name), u.name) AS name "
        "FROM scores s "
        "INNER JOIN users u ON u.id = s.userid "
        "LEFT JOIN clans c ON c.id = u.clan_id "
        "WHERE s.map_md5 = :map_md5 AND s.status = 2 "  # 2: =best score
        "AND (u.priv & 1 OR u.id = :user_id) AND mode = :mode",
    ]

    params: dict[str, Any] = {
        "map_md5": map_md5,
        "user_id": player.id,
        "mode": mode,
    }

    if leaderboard_type == LeaderboardType.Mods:
        query.append("AND s.mods = :mods")
        params["mods"] = mods
    elif leaderboard_type == LeaderboardType.Friends:
        query.append("AND s.userid IN :friends")
        params["friends"] = player.friends | {player.id}
    elif leaderboard_type == LeaderboardType.Country:
        query.append("AND u.country = :country")
        params["country"] = player.geoloc["country"]["acronym"]

    # TODO: customizability of the number of scores
    query.append("ORDER BY _score DESC LIMIT 50")

    score_rows = await app.state.services.database.fetch_all(
        " ".join(query),
        params,
    )

    if score_rows:  # None or []
        # fetch player's personal best score
        personal_best_score_row = await app.state.services.database.fetch_one(
            f"SELECT id, {scoring_metric} AS _score, "
            "max_combo, n50, n100, n300, "
            "nmiss, nkatu, ngeki, perfect, mods, "
            "UNIX_TIMESTAMP(play_time) time "
            "FROM scores "
            "WHERE map_md5 = :map_md5 AND mode = :mode "
            "AND userid = :user_id AND status = 2 "
            "ORDER BY _score DESC LIMIT 1",
            {"map_md5": map_md5, "mode": mode, "user_id": player.id},
        )

        if personal_best_score_row is not None:
            # calculate the rank of the score.
            p_best_rank = 1 + await app.state.services.database.fetch_val(
                "SELECT COUNT(*) FROM scores s "
                "INNER JOIN users u ON u.id = s.userid "
                "WHERE s.map_md5 = :map_md5 AND s.mode = :mode "
                "AND s.status = 2 AND u.priv & 1 "
                f"AND s.{scoring_metric} > :score",
                {
                    "map_md5": map_md5,
                    "mode": mode,
                    "score": personal_best_score_row["_score"],
                },
                column=0,  # COUNT(*)
            )

            # attach rank to personal best row
            personal_best_score_row["rank"] = p_best_rank
    else:
        score_rows = []
        personal_best_score_row = None

    return score_rows, personal_best_score_row


@router.get("/osu-osz2-getscores.php")
async def getScores(
    player: Player = Depends(authenticate_player_session(Query, "us", "ha")),
    requesting_from_editor_song_select: bool = Query(..., alias="s"),
    leaderboard_version: int = Query(..., alias="vv"),
    leaderboard_type: int = Query(..., alias="v", ge=0, le=4),
    map_md5: str = Query(..., alias="c", min_length=32, max_length=32),
    map_filename: str = Query(..., alias="f"),
    mode_arg: int = Query(..., alias="m", ge=0, le=3),
    map_set_id: int = Query(..., alias="i", ge=-1, le=2_147_483_647),
    mods_arg: int = Query(..., alias="mods", ge=0, le=2_147_483_647),
    map_package_hash: str = Query(..., alias="h"),  # TODO: further validation
    aqn_files_found: bool = Query(..., alias="a"),
) -> Response:
    if aqn_files_found:
        stacktrace = app.utils.get_appropriate_stacktrace()
        await app.state.services.log_strange_occurrence(stacktrace)

    # check if this md5 has already been  cached as
    # unsubmitted/needs update to reduce osu!api spam
    if map_md5 in app.state.cache.unsubmitted:
        return Response(b"-1|false")
    if map_md5 in app.state.cache.needs_update:
        return Response(b"1|false")

    if mods_arg & Mods.RELAX:
        if mode_arg == 3:  # rx!mania doesn't exist
            mods_arg &= ~Mods.RELAX
        else:
            mode_arg += 4
    elif mods_arg & Mods.AUTOPILOT:
        if mode_arg in (1, 2, 3):  # ap!catch, taiko and mania don't exist
            mods_arg &= ~Mods.AUTOPILOT
        else:
            mode_arg += 8

    mods = Mods(mods_arg)
    mode = GameMode(mode_arg)

    # attempt to update their stats if their
    # gm/gm-affecting-mods change at all.
    if mode != player.status.mode:
        player.status.mods = mods
        player.status.mode = mode

        if not player.restricted:
            app.state.sessions.players.enqueue(app.packets.user_stats(player))

    scoring_metric: Literal["pp", "score"] = (
        "pp" if mode >= GameMode.RELAX_OSU else "score"
    )

    bmap = await Beatmap.from_md5(map_md5, set_id=map_set_id)
    has_set_id = map_set_id > 0

    if not bmap:
        # map not found, figure out whether it needs an
        # update or isn't submitted using its filename.

        if has_set_id and map_set_id not in app.state.cache.beatmapset:
            # set not cached, it doesn't exist
            app.state.cache.unsubmitted.add(map_md5)
            return Response(b"-1|false")

        map_filename = unquote_plus(map_filename)  # TODO: is unquote needed?

        map_exists = False
        if has_set_id:
            # we can look it up in the specific set from cache
            for bmap in app.state.cache.beatmapset[map_set_id].maps:
                if map_filename == bmap.filename:
                    map_exists = True
                    break
            else:
                map_exists = False
        else:
            # we can't find it on the osu!api by md5,
            # and we don't have the set id, so we must
            # look it up in sql from the filename.
            map_exists = (
                await maps_repo.fetch_one(
                    filename=map_filename,
                )
                is not None
            )

        if map_exists:
            # map can be updated.
            app.state.cache.needs_update.add(map_md5)
            return Response(b"1|false")
        else:
            # map is unsubmitted.
            # add this map to the unsubmitted cache, so
            # that we don't have to make this request again.
            app.state.cache.unsubmitted.add(map_md5)
            return Response(b"-1|false")

    # we've found a beatmap for the request.

    if app.state.services.datadog:
        app.state.services.datadog.increment("bancho.leaderboards_served")  # type: ignore[no-untyped-call]

    if bmap.status < RankedStatus.Ranked:
        # only show leaderboards for ranked,
        # approved, qualified, or loved maps.
        return Response(f"{int(bmap.status)}|false".encode())

    # fetch scores & personal best
    # TODO: create a leaderboard cache
    if not requesting_from_editor_song_select:
        score_rows, personal_best_score_row = await get_leaderboard_scores(
            leaderboard_type,
            bmap.md5,
            mode,
            mods,
            player,
            scoring_metric,
        )
    else:
        score_rows = []
        personal_best_score_row = None

    # fetch beatmap rating
    map_ratings = await ratings_repo.fetch_many(
        map_md5=bmap.md5,
        page=None,
        page_size=None,
    )
    ratings = [row["rating"] for row in map_ratings]
    map_avg_rating = sum(ratings) / len(ratings) if ratings else 0.0

    ## construct response for osu! client

    response_lines: list[str] = [
        # NOTE: fa stands for featured artist (for the ones that may not know)
        # {ranked_status}|{serv_has_osz2}|{bid}|{bsid}|{len(scores)}|{fa_track_id}|{fa_license_text}
        f"{int(bmap.status)}|false|{bmap.id}|{bmap.set_id}|{len(score_rows)}|0|",
        # {offset}\n{beatmap_name}\n{rating}
        # TODO: server side beatmap offsets
        f"0\n{bmap.full_name}\n{map_avg_rating}",
    ]

    if not score_rows:
        response_lines.extend(("", ""))  # no scores, no personal best
        return Response("\n".join(response_lines).encode())

    if personal_best_score_row is not None:
        user_clan = (
            await clans_repo.fetch_one(id=player.clan_id)
            if player.clan_id is not None
            else None
        )
        display_name = (
            f"[{user_clan['tag']}] {player.name}"
            if user_clan is not None
            else player.name
        )
        response_lines.append(
            SCORE_LISTING_FMTSTR.format(
                **personal_best_score_row,
                name=display_name,
                userid=player.id,
                score=int(round(personal_best_score_row["_score"])),
                has_replay="1",
            ),
        )
    else:
        response_lines.append("")

    response_lines.extend(
        [
            SCORE_LISTING_FMTSTR.format(
                **s,
                score=int(round(s["_score"])),
                has_replay="1",
                rank=idx + 1,
            )
            for idx, s in enumerate(score_rows)
        ],
    )

    return Response("\n".join(response_lines).encode())
