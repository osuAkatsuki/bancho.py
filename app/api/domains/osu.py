"""osu: handle connections from web, api, and beyond?"""

from __future__ import annotations

import random
import secrets
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Sequence
from functools import cache
from pathlib import Path as SystemPath
from typing import Annotated
from typing import Any
from typing import Literal
from urllib.parse import unquote
from urllib.parse import unquote_plus

from fastapi import status
from fastapi.datastructures import FormData
from fastapi.datastructures import UploadFile
from fastapi.exceptions import HTTPException
from fastapi.param_functions import Depends
from fastapi.param_functions import File
from fastapi.param_functions import Form
from fastapi.param_functions import Header
from fastapi.param_functions import Path
from fastapi.param_functions import Query
from fastapi.requests import Request
from fastapi.responses import FileResponse
from fastapi.responses import ORJSONResponse
from fastapi.responses import RedirectResponse
from fastapi.responses import Response
from fastapi.routing import APIRouter
from starlette.datastructures import UploadFile as StarletteUploadFile

import app.packets
import app.settings
import app.state
import app.utils
from app import encryption
from app.adapters.score_submission import REPLAYS_PATH
from app.api import dependencies as api_dependencies
from app.constants.beatmap_statuses import RankedStatus
from app.constants.clientflags import LastFMFlags
from app.constants.gamemodes import GameMode
from app.constants.leaderboard_types import LeaderboardType
from app.constants.mods import Mods
from app.constants.privileges import Privileges
from app.logging import Ansi
from app.logging import log
from app.objects import models
from app.objects.beatmap import Beatmap
from app.objects.player import ModeData
from app.objects.player import Player
from app.objects.score import Score
from app.repositories.achievements import Achievement
from app.services.osu_web import AccountRegistrationService
from app.services.osu_web import AddFavouriteResult
from app.services.osu_web import BeatmapInfoService
from app.services.osu_web import BeatmapRatingResultCode
from app.services.osu_web import BeatmapRatingService
from app.services.osu_web import BeatmapSetService
from app.services.osu_web import CommentsService
from app.services.osu_web import FavouritesService
from app.services.osu_web import MailReadService
from app.services.osu_web import OsuLeaderboardSupportService
from app.services.score_leaderboards import ScoreLeaderboardsService
from app.services.score_submission import ScoreSubmissionError
from app.services.score_submission import ScoreSubmissionErrorCode
from app.services.score_submission import ScoreSubmissionRequest
from app.services.score_submission import ScoreSubmissionService

BEATMAPS_PATH = SystemPath.cwd() / ".data/osu"
SCREENSHOTS_PATH = SystemPath.cwd() / ".data/ss"


router = APIRouter(
    tags=["osu! web API"],
    default_response_class=Response,
)


@cache
def authenticate_player_session(
    param_function: Callable[..., Any],
    username_alias: str = "u",
    pw_md5_alias: str = "p",
    err: Any | None = None,
) -> Callable[[str, str], Awaitable[Player]]:
    async def wrapper(
        username: str = param_function(..., alias=username_alias),
        pw_md5: str = param_function(..., alias=pw_md5_alias),
    ) -> Player:
        player = await app.state.sessions.players.from_login(
            name=unquote(username),
            pw_md5=pw_md5,
        )
        if player:
            return player

        # player login incorrect
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=err,
        )

    return wrapper


""" /web/ handlers """

# Unhandled endpoints:
# POST /web/osu-error.php
# POST /web/osu-session.php
# POST /web/osu-osz2-bmsubmit-post.php
# POST /web/osu-osz2-bmsubmit-upload.php
# GET /web/osu-osz2-bmsubmit-getid.php
# GET /web/osu-get-beatmap-topic.php


@router.post("/web/osu-screenshot.php")
async def osuScreenshot(
    player: Player = Depends(authenticate_player_session(Form, "u", "p")),
    endpoint_version: int = Form(..., alias="v"),
    screenshot_file: UploadFile = File(..., alias="ss"),
) -> Response:
    with memoryview(await screenshot_file.read()) as screenshot_view:
        # png sizes: 1080p: ~300-800kB | 4k: ~1-2mB
        if len(screenshot_view) > (4 * 1024 * 1024):
            return Response(
                content=b"Screenshot file too large.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if endpoint_version != 1:
            await app.state.services.log_strange_occurrence(
                f"Incorrect endpoint version (/web/osu-screenshot.php v{endpoint_version})",
            )

        if app.utils.has_jpeg_headers_and_trailers(screenshot_view):
            extension = "jpeg"
        elif app.utils.has_png_headers_and_trailers(screenshot_view):
            extension = "png"
        else:
            return Response(
                content=b"Invalid file type",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        while True:
            filename = f"{secrets.token_urlsafe(6)}.{extension}"
            ss_file = SCREENSHOTS_PATH / filename
            if not ss_file.exists():
                break

        with ss_file.open("wb") as f:
            f.write(screenshot_view)

    log(f"{player} uploaded {filename}.")
    return Response(filename.encode())


@router.get("/web/osu-getfriends.php")
async def osuGetFriends(
    player: Player = Depends(authenticate_player_session(Query, "u", "h")),
) -> Response:
    return Response("\n".join(map(str, player.friends)).encode())


def bancho_to_osuapi_status(bancho_status: int) -> int:
    return {
        0: 0,
        2: 1,
        3: 2,
        4: 3,
        5: 4,
    }[bancho_status]


@router.post("/web/osu-getbeatmapinfo.php")
async def osuGetBeatmapInfo(
    form_data: models.OsuBeatmapRequestForm,
    *,
    player: Player = Depends(authenticate_player_session(Query, "u", "h")),
    beatmap_info_service: Annotated[
        BeatmapInfoService,
        Depends(api_dependencies.get_beatmap_info_service),
    ],
) -> Response:
    num_requests = len(form_data.Filenames) + len(form_data.Ids)
    log(f"{player} requested info for {num_requests} maps.", Ansi.LCYAN)

    response_lines: list[str] = []

    for beatmap_info in await beatmap_info_service.fetch_beatmap_info(
        filenames=form_data.Filenames,
        player_id=player.id,
        vanilla_mode=player.status.mode.as_vanilla,
    ):
        response_lines.append(
            "{i}|{id}|{set_id}|{md5}|{status}|{grades}".format(
                i=beatmap_info.index,
                id=beatmap_info.id,
                set_id=beatmap_info.set_id,
                md5=beatmap_info.md5,
                status=bancho_to_osuapi_status(beatmap_info.status),
                grades="|".join(beatmap_info.grades),
            ),
        )

    if form_data.Ids:  # still have yet to see this used
        await app.state.services.log_strange_occurrence(
            f"{player} requested map(s) info by id ({form_data.Ids})",
        )

    return Response("\n".join(response_lines).encode())


@router.get("/web/osu-getfavourites.php")
async def osuGetFavourites(
    *,
    player: Player = Depends(authenticate_player_session(Query, "u", "h")),
    favourites_service: Annotated[
        FavouritesService,
        Depends(api_dependencies.get_favourites_service),
    ],
) -> Response:
    favourite_set_ids = await favourites_service.fetch_favourite_set_ids(player.id)
    return Response(
        "\n".join([str(map_set_id) for map_set_id in favourite_set_ids]).encode(),
    )


@router.get("/web/osu-addfavourite.php")
async def osuAddFavourite(
    *,
    player: Player = Depends(authenticate_player_session(Query, "u", "h")),
    map_set_id: int = Query(..., alias="a"),
    favourites_service: Annotated[
        FavouritesService,
        Depends(api_dependencies.get_favourites_service),
    ],
) -> Response:
    result = await favourites_service.add_favourite(
        player_id=player.id,
        map_set_id=map_set_id,
    )
    if result is AddFavouriteResult.ALREADY_FAVOURITED:
        return Response(b"You've already favourited this beatmap!")

    return Response(b"Added favourite!")


@router.get("/web/lastfm.php")
async def lastFM(
    action: Literal["scrobble", "np"],
    beatmap_id_or_hidden_flag: str = Query(
        ...,
        description=(
            "This flag is normally a beatmap ID, but is also "
            "used as a hidden anticheat flag within osu!"
        ),
        alias="b",
    ),
    player: Player = Depends(authenticate_player_session(Query, "us", "ha")),
) -> Response:
    if beatmap_id_or_hidden_flag[0] != "a":
        # not anticheat related, tell the
        # client not to send any more for now.
        return Response(b"-3")

    flags = LastFMFlags(int(beatmap_id_or_hidden_flag[1:]))

    if flags & (LastFMFlags.HQ_ASSEMBLY | LastFMFlags.HQ_FILE):
        # Player is currently running hq!osu; could possibly
        # be a separate client, buuuut prooobably not lol.

        await player.restrict(
            admin=app.state.sessions.bot,
            reason=f"hq!osu running ({flags})",
        )

        # refresh their client state
        if player.is_online:
            player.logout()

        return Response(b"-3")

    if flags & LastFMFlags.REGISTRY_EDITS:
        # Player has registry edits left from
        # hq!osu's multiaccounting tool. This
        # does not necessarily mean they are
        # using it now, but they have in the past.

        if random.randrange(32) == 0:
            # Random chance (1/32) for a ban.
            await player.restrict(
                admin=app.state.sessions.bot,
                reason="hq!osu relife 1/32",
            )

            # refresh their client state
            if player.is_online:
                player.logout()

            return Response(b"-3")

        player.enqueue(
            app.packets.notification(
                "\n".join(
                    [
                        "Hey!",
                        "It appears you have hq!osu's multiaccounting tool (relife) enabled.",
                        "This tool leaves a change in your registry that the osu! client can detect.",
                        "Please re-install relife and disable the program to avoid any restrictions.",
                    ],
                ),
            ),
        )

        player.logout()

        return Response(b"-3")

    """ These checks only worked for ~5 hours from release. rumoi's quick!
    if flags & (
        LastFMFlags.SDL2_LIBRARY
        | LastFMFlags.OPENSSL_LIBRARY
        | LastFMFlags.AQN_MENU_SAMPLE
    ):
        # AQN has been detected in the client, either
        # through the 'libeay32.dll' library being found
        # onboard, or from the menu sound being played in
        # the AQN menu while being in an inappropriate menu
        # for the context of the sound effect.
        pass
    """

    return Response(b"")


DIRECT_SET_INFO_FMTSTR = (
    "{SetID}.osz|{Artist}|{Title}|{Creator}|"
    "{RankedStatus}|10.0|{LastUpdate}|{SetID}|"
    "0|{HasVideo}|0|0|0|{diffs}"  # 0s are threadid, has_story,
    # filesize, filesize_novid.
)

DIRECT_MAP_INFO_FMTSTR = (
    "[{DifficultyRating:.2f}⭐] {DiffName} "
    "{{cs: {CS} / od: {OD} / ar: {AR} / hp: {HP}}}@{Mode}"
)


@router.get("/web/osu-search.php")
async def osuSearchHandler(
    player: Player = Depends(authenticate_player_session(Query, "u", "h")),
    ranked_status: int = Query(..., alias="r", ge=0, le=8),
    query: str = Query(..., alias="q"),
    mode: int = Query(..., alias="m", ge=-1, le=3),  # -1 for all
    page_num: int = Query(..., alias="p"),
) -> Response:
    params: dict[str, Any] = {"amount": 100, "offset": page_num * 100}

    # eventually we could try supporting these,
    # but it mostly depends on the mirror.
    if query not in ("Newest", "Top+Rated", "Most+Played"):
        params["query"] = query

    if mode != -1:  # -1 for all
        params["mode"] = mode

    if ranked_status != 4:  # 4 for all
        # convert to osu!api status
        params["status"] = RankedStatus.from_osudirect(ranked_status).osu_api

    response = await app.state.services.http_client.get(
        app.settings.MIRROR_SEARCH_ENDPOINT,
        params=params,
    )
    if response.status_code != status.HTTP_200_OK:
        return Response(b"-1\nFailed to retrieve data from the beatmap mirror.")

    result = response.json()

    lresult = len(result)  # send over 100 if we receive
    # 100 matches, so the client
    # knows there are more to get
    ret = [f"{'101' if lresult == 100 else lresult}"]
    for bmapset in result:
        if bmapset["ChildrenBeatmaps"] is None:
            continue

        # some mirrors use a true/false instead of 0 or 1
        bmapset["HasVideo"] = int(bmapset["HasVideo"])

        diff_sorted_maps = sorted(
            bmapset["ChildrenBeatmaps"],
            key=lambda m: m["DifficultyRating"],
        )

        def handle_invalid_characters(s: str) -> str:
            # XXX: this is a bug that exists on official servers (lmao)
            # | is used to delimit the set data, so the difficulty name
            # cannot contain this or it will be ignored. we fix it here
            # by using a different character.
            return s.replace("|", "I")

        diffs_str = ",".join(
            [
                DIRECT_MAP_INFO_FMTSTR.format(
                    DifficultyRating=row["DifficultyRating"],
                    DiffName=handle_invalid_characters(row["DiffName"]),
                    CS=row["CS"],
                    OD=row["OD"],
                    AR=row["AR"],
                    HP=row["HP"],
                    Mode=row["Mode"],
                )
                for row in diff_sorted_maps
            ],
        )

        ret.append(
            DIRECT_SET_INFO_FMTSTR.format(
                Artist=handle_invalid_characters(bmapset["Artist"]),
                Title=handle_invalid_characters(bmapset["Title"]),
                Creator=bmapset["Creator"],
                RankedStatus=bmapset["RankedStatus"],
                LastUpdate=bmapset["LastUpdate"],
                SetID=bmapset["SetID"],
                HasVideo=bmapset["HasVideo"],
                diffs=diffs_str,
            ),
        )

    return Response("\n".join(ret).encode())


# TODO: video support (needs db change)
@router.get("/web/osu-search-set.php")
async def osuSearchSetHandler(
    *,
    player: Player = Depends(authenticate_player_session(Query, "u", "h")),
    map_set_id: int | None = Query(None, alias="s"),
    map_id: int | None = Query(None, alias="b"),
    checksum: str | None = Query(None, alias="c"),
    beatmap_set_service: Annotated[
        BeatmapSetService,
        Depends(api_dependencies.get_beatmap_set_service),
    ],
) -> Response:
    # Since we only need set-specific data, we can basically
    # just do same query with either bid or bsid.

    if map_set_id is not None:
        # this is just a normal request
        bmapset = await beatmap_set_service.fetch_set_info(set_id=map_set_id)
    elif map_id is not None:
        bmapset = await beatmap_set_service.fetch_set_info(map_id=map_id)
    elif checksum is not None:
        bmapset = await beatmap_set_service.fetch_set_info(md5=checksum)
    else:
        return Response(b"")  # invalid args

    if bmapset is None:
        # TODO: get from osu!
        return Response(b"")

    rating = 10.0  # TODO: real data

    return Response(
        (
            "{set_id}.osz|{artist}|{title}|{creator}|"
            "{status}|{rating:.1f}|{last_update}|{set_id}|"
            "0|0|0|0|0"
        )
        .format(**bmapset, rating=rating)
        .encode(),
    )
    # 0s are threadid, has_vid, has_story, filesize, filesize_novid


def parse_form_data_score_params(
    score_data: FormData,
) -> tuple[bytes, StarletteUploadFile] | None:
    """Parse the score data, and replay file
    from the form data's 'score' parameters."""
    try:
        score_parts = score_data.getlist("score")
        assert len(score_parts) == 2, "Invalid score data"

        score_data_b64 = score_data.getlist("score")[0]
        assert isinstance(score_data_b64, str), "Invalid score data"
        replay_file = score_data.getlist("score")[1]
        assert isinstance(replay_file, StarletteUploadFile), "Invalid replay data"
    except AssertionError as exc:
        log(f"Failed to validate score multipart data: ({exc.args[0]})", Ansi.LRED)
        return None
    else:
        return (
            score_data_b64.encode(),
            replay_file,
        )


def chart_entry(
    name: str,
    before: float | int | None,
    after: float | int | None,
) -> str:
    return f"{name}Before:{before or ''}|{name}After:{after or ''}"


def format_achievement_string(file: str, name: str, description: str) -> str:
    return f"{file}+{name}+{description}"


def format_achievements(achievements: Sequence[Achievement]) -> str:
    return "/".join(
        format_achievement_string(
            achievement["file"],
            achievement["name"],
            achievement["desc"],
        )
        for achievement in achievements
    )


def build_submission_charts(
    *,
    score: Score,
    previous_stats: ModeData,
    current_stats: ModeData,
    achievements: Sequence[Achievement],
    domain: str,
) -> bytes:
    assert score.bmap is not None
    assert score.player is not None

    if score.prev_best:
        beatmap_ranking_chart_entries = (
            chart_entry("rank", score.prev_best.rank, score.rank),
            chart_entry("rankedScore", score.prev_best.score, score.score),
            chart_entry("totalScore", score.prev_best.score, score.score),
            chart_entry("maxCombo", score.prev_best.max_combo, score.max_combo),
            chart_entry("accuracy", round(score.prev_best.acc, 2), round(score.acc, 2)),
            chart_entry("pp", score.prev_best.pp, score.pp),
        )
    else:
        beatmap_ranking_chart_entries = (
            chart_entry("rank", None, score.rank),
            chart_entry("rankedScore", None, score.score),
            chart_entry("totalScore", None, score.score),
            chart_entry("maxCombo", None, score.max_combo),
            chart_entry("accuracy", None, round(score.acc, 2)),
            chart_entry("pp", None, score.pp),
        )

    overall_ranking_chart_entries = (
        chart_entry("rank", previous_stats.rank, current_stats.rank),
        chart_entry("rankedScore", previous_stats.rscore, current_stats.rscore),
        chart_entry("totalScore", previous_stats.tscore, current_stats.tscore),
        chart_entry("maxCombo", previous_stats.max_combo, current_stats.max_combo),
        chart_entry(
            "accuracy",
            round(previous_stats.acc, 2),
            round(current_stats.acc, 2),
        ),
        chart_entry("pp", previous_stats.pp, current_stats.pp),
    )

    submission_charts = [
        # beatmap info chart
        f"beatmapId:{score.bmap.id}",
        f"beatmapSetId:{score.bmap.set_id}",
        f"beatmapPlaycount:{score.bmap.plays}",
        f"beatmapPasscount:{score.bmap.passes}",
        f"approvedDate:{score.bmap.last_update}",
        "\n",
        # beatmap ranking chart
        "chartId:beatmap",
        f"chartUrl:{score.bmap.set.url}",
        "chartName:Beatmap Ranking",
        *beatmap_ranking_chart_entries,
        f"onlineScoreId:{score.id}",
        "\n",
        # overall ranking chart
        "chartId:overall",
        f"chartUrl:https://{domain}/u/{score.player.id}",
        "chartName:Overall Ranking",
        *overall_ranking_chart_entries,
        f"achievements-new:{format_achievements(achievements)}",
    ]

    return "|".join(submission_charts).encode()


def build_score_submission_response(
    *,
    score: Score,
    previous_stats: ModeData,
    current_stats: ModeData,
    domain: str,
    unlocked_achievements: Sequence[Achievement],
) -> bytes:
    if not score.passed:  # TODO: check if this is correct
        return b"error: no"

    assert score.bmap is not None
    assert score.player is not None

    return build_submission_charts(
        score=score,
        previous_stats=previous_stats,
        current_stats=current_stats,
        achievements=unlocked_achievements,
        domain=domain,
    )


def build_score_submission_error_response(
    error: ScoreSubmissionError,
) -> bytes:
    if error.code is ScoreSubmissionErrorCode.BEATMAP_NOT_FOUND:
        return b"error: beatmap"
    if error.code is ScoreSubmissionErrorCode.PLAYER_NOT_FOUND:
        # Player is not online, return nothing so that their
        # client will retry submission when they log in.
        return b""
    if error.code is ScoreSubmissionErrorCode.DUPLICATE_SUBMISSION:
        return b"error: no"

    raise ValueError(f"Unexpected score submission error: {error.code!r}")


@router.post("/web/osu-submit-modular-selector.php")
async def osuSubmitModularSelector(
    request: Request,
    score_submission_service: Annotated[
        ScoreSubmissionService,
        Depends(api_dependencies.get_score_submission_service),
    ],
    # TODO: should token be allowed
    # through but ac'd if not found?
    # TODO: validate token format
    # TODO: save token in the database
    token: str = Header(...),
    # TODO: do ft & st contain pauses?
    exited_out: bool = Form(..., alias="x"),
    fail_time: int = Form(..., alias="ft"),
    visual_settings_b64: bytes = Form(..., alias="fs"),
    updated_beatmap_hash: str = Form(..., alias="bmk"),
    storyboard_md5: str | None = Form(None, alias="sbk"),
    iv_b64: bytes = Form(..., alias="iv"),
    unique_ids: str = Form(..., alias="c1"),
    score_time: int = Form(..., alias="st"),
    pw_md5: str = Form(..., alias="pass"),
    osu_version: str = Form(..., alias="osuver"),
    client_hash_b64: bytes = Form(..., alias="s"),
    fl_cheat_screenshot: bytes | None = File(None, alias="i"),
) -> Response:
    """Handle a score submission from an osu! client with an active session."""

    if fl_cheat_screenshot:
        stacktrace = app.utils.get_appropriate_stacktrace()
        await app.state.services.log_strange_occurrence(stacktrace)

    # NOTE: the bancho protocol uses the "score" parameter name for both
    # the base64'ed score data, and the replay file in the multipart
    # starlette/fastapi do not support this, so we've moved it out
    score_parameters = parse_form_data_score_params(await request.form())
    if score_parameters is None:
        return Response(b"")

    # extract the score data and replay file from the score data
    score_data_b64, replay_file = score_parameters

    # decrypt the score data (aes)
    score_data, client_hash_decoded = encryption.decrypt_score_aes_data(
        score_data_b64,
        client_hash_b64,
        iv_b64,
        osu_version,
    )

    submitted_score = await score_submission_service.submit_score(
        ScoreSubmissionRequest(
            score_data=score_data,
            password_md5=pw_md5,
            osu_version=osu_version,
            client_hash=client_hash_decoded,
            unique_ids=unique_ids,
            storyboard_md5=storyboard_md5,
            updated_beatmap_hash=updated_beatmap_hash,
            score_time=score_time,
            fail_time=fail_time,
            replay_file=replay_file,
        ),
    )
    if isinstance(submitted_score, ScoreSubmissionError):
        return Response(build_score_submission_error_response(submitted_score))

    response = build_score_submission_response(
        score=submitted_score.score,
        previous_stats=submitted_score.previous_stats,
        current_stats=submitted_score.current_stats,
        domain=app.settings.DOMAIN,
        unlocked_achievements=submitted_score.unlocked_achievements,
    )

    return Response(response)


@router.get("/web/osu-getreplay.php")
async def getReplay(
    player: Player = Depends(authenticate_player_session(Query, "u", "h")),
    mode: int = Query(..., alias="m", ge=0, le=3),
    score_id: int = Query(..., alias="c", min=0, max=9_223_372_036_854_775_807),
) -> Response:
    score = await Score.from_sql(score_id)
    if not score:
        return Response(b"", status_code=404)

    file = REPLAYS_PATH / f"{score_id}.osr"
    if not file.exists():
        return Response(b"", status_code=404)

    # increment replay views for this score
    if score.player is not None and player.id != score.player.id:
        app.state.loop.create_task(score.increment_replay_views())  # type: ignore[unused-awaitable]

    return FileResponse(file)


@router.get("/web/osu-rate.php")
async def osuRate(
    *,
    player: Player = Depends(
        authenticate_player_session(Query, "u", "p", err=b"auth fail"),
    ),
    map_md5: str = Query(..., alias="c", min_length=32, max_length=32),
    rating: int | None = Query(None, alias="v", ge=1, le=10),
    beatmap_rating_service: Annotated[
        BeatmapRatingService,
        Depends(api_dependencies.get_beatmap_rating_service),
    ],
) -> Response:
    rating_result = await beatmap_rating_service.rate_or_check(
        player_id=player.id,
        map_md5=map_md5,
        rating=rating,
    )
    if rating_result.code is BeatmapRatingResultCode.NO_EXIST:
        return Response(b"no exist")
    if rating_result.code is BeatmapRatingResultCode.NOT_RANKED:
        return Response(b"not ranked")
    if rating_result.code is BeatmapRatingResultCode.CAN_RATE:
        return Response(b"ok")

    # send back the average rating
    assert rating_result.average_rating is not None
    return Response(f"alreadyvoted\n{rating_result.average_rating}".encode())


SCORE_LISTING_FMTSTR = (
    "{id}|{name}|{score}|{max_combo}|"
    "{n50}|{n100}|{n300}|{nmiss}|{nkatu}|{ngeki}|"
    "{perfect}|{mods}|{userid}|{rank}|{time}|{has_replay}"
)


@router.get("/web/osu-osz2-getscores.php")
async def getScores(
    *,
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
    score_leaderboards_service: Annotated[
        ScoreLeaderboardsService,
        Depends(api_dependencies.get_score_leaderboards_service),
    ],
    leaderboard_support_service: Annotated[
        OsuLeaderboardSupportService,
        Depends(api_dependencies.get_osu_leaderboard_support_service),
    ],
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
            map_exists = await leaderboard_support_service.map_exists_by_filename(
                map_filename,
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
        leaderboard_scores = await score_leaderboards_service.fetch_leaderboard_scores(
            leaderboard_type=leaderboard_type,
            map_md5=bmap.md5,
            mode=mode,
            mods=mods,
            player=player,
            scoring_metric=scoring_metric,
        )
        score_rows = leaderboard_scores.score_rows
        personal_best_score_row = leaderboard_scores.personal_best_score_row
    else:
        score_rows = []
        personal_best_score_row = None

    # fetch beatmap rating
    map_avg_rating = await leaderboard_support_service.fetch_map_rating_average(
        bmap.md5,
    )

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
        user_clan_tag = (
            await leaderboard_support_service.fetch_clan_tag(player.clan_id)
            if player.clan_id is not None
            else None
        )
        display_name = (
            f"[{user_clan_tag}] {player.name}"
            if user_clan_tag is not None
            else player.name
        )
        response_lines.append(
            SCORE_LISTING_FMTSTR.format(
                **personal_best_score_row,
                name=display_name,
                userid=player.id,
                score=int(round(personal_best_score_row["leaderboard_value"])),
                has_replay="1",
            ),
        )
    else:
        response_lines.append("")

    response_lines.extend(
        [
            SCORE_LISTING_FMTSTR.format(
                **s,
                score=int(round(s["leaderboard_value"])),
                has_replay="1",
                rank=idx + 1,
            )
            for idx, s in enumerate(score_rows)
        ],
    )

    return Response("\n".join(response_lines).encode())


@router.post("/web/osu-comment.php")
async def osuComment(
    *,
    player: Player = Depends(authenticate_player_session(Form, "u", "p")),
    map_id: int = Form(..., alias="b"),
    map_set_id: int = Form(..., alias="s"),
    score_id: int = Form(..., alias="r", ge=0, le=9_223_372_036_854_775_807),
    mode_vn: int = Form(..., alias="m", ge=0, le=3),
    action: Literal["get", "post"] = Form(..., alias="a"),
    # only sent for post
    target: Literal["song", "map", "replay"] | None = Form(None),
    colour: str | None = Form(None, alias="f", min_length=6, max_length=6),
    start_time: int | None = Form(None, alias="starttime"),
    comment: str | None = Form(None, min_length=1, max_length=80),
    comments_service: Annotated[
        CommentsService,
        Depends(api_dependencies.get_comments_service),
    ],
) -> Response:
    if action == "get":
        # client is requesting all comments
        comments = await comments_service.fetch_relevant_to_replay(
            score_id=score_id,
            map_set_id=map_set_id,
            map_id=map_id,
        )

        ret: list[str] = []

        for cmt in comments:
            # note: this implementation does not support
            #       "player" or "creator" comment colours
            if cmt["priv"] & Privileges.NOMINATOR:
                fmt = "bat"
            elif cmt["priv"] & Privileges.DONATOR:
                fmt = "supporter"
            else:
                fmt = ""

            if cmt["colour"]:
                fmt += f'|{cmt["colour"]}'

            ret.append(
                "{time}\t{target_type}\t{fmt}\t{comment}".format(fmt=fmt, **cmt),
            )

        player.update_latest_activity_soon()
        return Response("\n".join(ret).encode())

    elif action == "post":
        # client is submitting a new comment

        # validate all required params are provided
        assert target is not None
        assert start_time is not None
        assert comment is not None

        if colour and not player.priv & Privileges.DONATOR:
            # only supporters can use colours.
            colour = None

            log(
                f"User {player} attempted to use a coloured comment without "
                "supporter status. Submitting comment without a colour.",
            )

        await comments_service.create_comment(
            target=target,
            map_set_id=map_set_id,
            map_id=map_id,
            score_id=score_id,
            player_id=player.id,
            start_time=start_time,
            comment=comment,
            colour=colour,
        )

        player.update_latest_activity_soon()

    return Response(b"")  # empty resp is fine


@router.get("/web/osu-markasread.php")
async def osuMarkAsRead(
    *,
    player: Player = Depends(authenticate_player_session(Query, "u", "h")),
    channel: str = Query(..., min_length=0, max_length=32),
    mail_read_service: Annotated[
        MailReadService,
        Depends(api_dependencies.get_mail_read_service),
    ],
) -> Response:
    target_name = unquote(channel)  # TODO: unquote needed?
    if not target_name:
        log(
            f"User {player} attempted to mark a channel as read without a target.",
            Ansi.LYELLOW,
        )
        return Response(b"")  # no channel specified

    await mail_read_service.mark_conversation_with_player_as_read(
        player_id=player.id,
        target_name=target_name,
    )

    return Response(b"")


@router.get("/web/osu-getseasonal.php")
async def osuSeasonal() -> Response:
    return ORJSONResponse(app.settings.SEASONAL_BGS)


@router.get("/web/bancho_connect.php")
async def banchoConnect(
    # NOTE: this is disabled as this endpoint can be called
    #       before a player has been granted a session
    # player: Player = Depends(authenticate_player_session(Query, "u", "h")),
    osu_ver: str = Query(..., alias="v"),
    active_endpoint: str | None = Query(None, alias="fail"),
    net_framework_vers: str | None = Query(None, alias="fx"),  # delimited by |
    client_hash: str | None = Query(None, alias="ch"),
    retrying: bool | None = Query(None, alias="retry"),  # '0' or '1'
) -> Response:
    return Response(b"")


@router.get("/web/check-updates.php")
async def checkUpdates(
    request: Request,
    action: Literal["check", "path", "error"],
    stream: Literal["cuttingedge", "stable40", "beta40", "stable"],
) -> Response:
    return Response(b"")


""" Misc handlers """


if app.settings.REDIRECT_OSU_URLS:
    # NOTE: this will likely be removed with the addition of a frontend.
    async def osu_redirect(request: Request, _: int = Path(...)) -> Response:
        return RedirectResponse(
            url=f"https://osu.ppy.sh{request['path']}",
            status_code=status.HTTP_301_MOVED_PERMANENTLY,
        )

    for pattern in (
        "/beatmapsets/{_}",
        "/beatmaps/{_}",
        "/beatmapsets/{_}/discussion",
        "/community/forums/topics/{_}",
    ):
        router.get(pattern)(osu_redirect)


@router.get("/ss/{screenshot_id}.{extension}")
async def get_screenshot(
    screenshot_id: str = Path(..., pattern=r"[a-zA-Z0-9-_]{8}"),
    extension: Literal["jpg", "jpeg", "png"] = Path(...),
) -> Response:
    """Serve a screenshot from the server, by filename."""
    screenshot_path = SCREENSHOTS_PATH / f"{screenshot_id}.{extension}"

    if not screenshot_path.exists():
        return ORJSONResponse(
            content={"status": "Screenshot not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if extension in ("jpg", "jpeg"):
        media_type = "image/jpeg"
    elif extension == "png":
        media_type = "image/png"
    else:
        media_type = None

    return FileResponse(
        path=screenshot_path,
        media_type=media_type,
    )


@router.get("/d/{map_set_id}")
async def get_osz(
    map_set_id: str = Path(...),
) -> Response:
    """Handle a map download request (osu.ppy.sh/d/*)."""
    no_video = map_set_id[-1] == "n"
    if no_video:
        map_set_id = map_set_id[:-1]

    query_str = f"{map_set_id}?n={int(not no_video)}"

    return RedirectResponse(
        url=f"{app.settings.MIRROR_DOWNLOAD_ENDPOINT}/{query_str}",
        status_code=status.HTTP_301_MOVED_PERMANENTLY,
    )


@router.get("/web/maps/{map_filename}")
async def get_updated_beatmap(
    request: Request,
    map_filename: str,
    host: str = Header(...),
) -> Response:
    """Send the latest .osu file the server has for a given map."""
    if host == "osu.ppy.sh":
        return Response("bancho.py only supports the -devserver connection method")

    return RedirectResponse(
        url=f"https://osu.ppy.sh{request['raw_path'].decode()}",
        status_code=status.HTTP_301_MOVED_PERMANENTLY,
    )


@router.get("/p/doyoureallywanttoaskpeppy")
async def peppyDMHandler() -> Response:
    return Response(
        content=(
            b"This user's ID is usually peppy's (when on bancho), "
            b"and is blocked from being messaged by the osu! client."
        ),
    )


""" ingame registration """

INGAME_REGISTRATION_DISALLOWED_ERROR = {
    "form_error": {
        "user": {
            "password": [
                "In-game registration is disabled. Please register on the website.",
            ],
        },
    },
}


@router.post("/users")
async def register_account(
    request: Request,
    account_registration_service: Annotated[
        AccountRegistrationService,
        Depends(api_dependencies.get_account_registration_service),
    ],
    username: str = Form(..., alias="user[username]"),
    email: str = Form(..., alias="user[user_email]"),
    pw_plaintext: str = Form(..., alias="user[password]"),
    check: int = Form(...),
    # XXX: require/validate these headers; they are used later
    # on in the registration process for resolving geolocation
    forwarded_ip: str = Header(..., alias="X-Forwarded-For"),
    real_ip: str = Header(..., alias="X-Real-IP"),
) -> Response:
    if not all((username, email, pw_plaintext)):
        return Response(
            content=b"Missing required params",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Disable in-game registration if enabled
    if app.settings.DISALLOW_INGAME_REGISTRATION:
        return ORJSONResponse(
            content=INGAME_REGISTRATION_DISALLOWED_ERROR,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    errors = await account_registration_service.validate_registration(
        username=username,
        email=email,
        password=pw_plaintext,
    )

    if errors:
        # we have errors to send back, send them back delimited by newlines.
        formatted_errors = {k: ["\n".join(v)] for k, v in errors.items()}
        errors_full = {"form_error": {"user": formatted_errors}}
        return ORJSONResponse(
            content=errors_full,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if check == 0:
        # the client isn't just checking values,
        # they want to register the account now.
        registered_account = await account_registration_service.create_account(
            username=username,
            email=email,
            password=pw_plaintext,
            request_headers=request.headers,
        )
        player = registered_account.player

        if app.state.services.datadog:
            app.state.services.datadog.increment("bancho.registrations")  # type: ignore[no-untyped-call]

        log(f"<{username} ({player['id']})> has registered!", Ansi.LGREEN)

    return Response(content=b"ok")  # success


@router.post("/difficulty-rating")
async def difficultyRatingHandler(request: Request) -> Response:
    return RedirectResponse(
        url=f"https://osu.ppy.sh{request['path']}",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )
