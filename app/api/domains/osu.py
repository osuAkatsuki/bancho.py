"""osu: handle connections from web, api, and beyond?"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path as SystemPath
from typing import Annotated
from typing import Any
from typing import Literal
from urllib.parse import unquote

from fastapi import status
from fastapi.datastructures import FormData
from fastapi.datastructures import UploadFile
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

import app.settings
import app.state
import app.utils
from app import encryption
from app.api import dependencies as api_dependencies
from app.constants.privileges import Privileges
from app.logging import Ansi
from app.logging import log
from app.objects import models
from app.objects.player import ModeData
from app.objects.player import Player
from app.objects.score import Score
from app.repositories.achievements import Achievement
from app.services.accounts import AccountRegistrationResultCode
from app.services.accounts import AccountRegistrationService
from app.services.beatmap_leaderboards import BeatmapLeaderboardRequest
from app.services.beatmap_leaderboards import BeatmapLeaderboardResult
from app.services.beatmap_leaderboards import BeatmapLeaderboardResultCode
from app.services.beatmap_leaderboards import BeatmapLeaderboardService
from app.services.client_integrity import ClientIntegrityResult
from app.services.client_integrity import ClientIntegrityService
from app.services.comments import CommentsService
from app.services.direct_search import DirectSearchResult
from app.services.direct_search import DirectSearchResultCode
from app.services.direct_search import DirectSearchService
from app.services.favourites import AddFavouriteResult
from app.services.favourites import FavouritesService
from app.services.mail import MailReadService
from app.services.maps import BeatmapInfoService
from app.services.maps import BeatmapRatingResultCode
from app.services.maps import BeatmapRatingService
from app.services.maps import BeatmapSetService
from app.services.osu_client_authentication import OsuClientAuthenticationService
from app.services.replays import ReplayResultCode
from app.services.replays import ReplayService
from app.services.score_submission import ScoreSubmissionError
from app.services.score_submission import ScoreSubmissionErrorCode
from app.services.score_submission import ScoreSubmissionRequest
from app.services.score_submission import ScoreSubmissionService
from app.services.screenshots import ScreenshotService
from app.services.screenshots import ScreenshotUploadResultCode

BEATMAPS_PATH = SystemPath.cwd() / ".data/osu"
SCREENSHOTS_PATH = SystemPath.cwd() / ".data/ss"


router = APIRouter(
    tags=["osu! web API"],
    default_response_class=Response,
)


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
    *,
    osu_client_authentication: Annotated[
        OsuClientAuthenticationService,
        Depends(api_dependencies.get_osu_client_authentication_service),
    ],
    username: str = Form(..., alias="u"),
    password_md5: str = Form(..., alias="p"),
    endpoint_version: int = Form(..., alias="v"),
    screenshot_file: UploadFile = File(..., alias="ss"),
    screenshot_service: Annotated[
        ScreenshotService,
        Depends(api_dependencies.get_screenshot_service),
    ],
) -> Response:
    player = await osu_client_authentication.authenticate_online_player(
        username=unquote(username),
        password_md5=password_md5,
    )
    if player is None:
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)

    result = await screenshot_service.upload_screenshot(
        player=player,
        endpoint_version=endpoint_version,
        screenshot_data=await screenshot_file.read(),
    )
    if result.code is ScreenshotUploadResultCode.FILE_TOO_LARGE:
        return Response(
            content=b"Screenshot file too large.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if result.code is ScreenshotUploadResultCode.INVALID_FILE_TYPE:
        return Response(
            content=b"Invalid file type",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    assert result.filename is not None
    return Response(result.filename.encode())


@router.get("/web/osu-getfriends.php")
async def osuGetFriends(
    *,
    osu_client_authentication: Annotated[
        OsuClientAuthenticationService,
        Depends(api_dependencies.get_osu_client_authentication_service),
    ],
    username: str = Query(..., alias="u"),
    password_md5: str = Query(..., alias="h"),
) -> Response:
    player = await osu_client_authentication.authenticate_online_player(
        username=unquote(username),
        password_md5=password_md5,
    )
    if player is None:
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)

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
    osu_client_authentication: Annotated[
        OsuClientAuthenticationService,
        Depends(api_dependencies.get_osu_client_authentication_service),
    ],
    username: str = Query(..., alias="u"),
    password_md5: str = Query(..., alias="h"),
    beatmap_info_service: Annotated[
        BeatmapInfoService,
        Depends(api_dependencies.get_beatmap_info_service),
    ],
) -> Response:
    player = await osu_client_authentication.authenticate_online_player(
        username=unquote(username),
        password_md5=password_md5,
    )
    if player is None:
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)

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
    osu_client_authentication: Annotated[
        OsuClientAuthenticationService,
        Depends(api_dependencies.get_osu_client_authentication_service),
    ],
    username: str = Query(..., alias="u"),
    password_md5: str = Query(..., alias="h"),
    favourites_service: Annotated[
        FavouritesService,
        Depends(api_dependencies.get_favourites_service),
    ],
) -> Response:
    player = await osu_client_authentication.authenticate_online_player(
        username=unquote(username),
        password_md5=password_md5,
    )
    if player is None:
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)

    favourite_set_ids = await favourites_service.fetch_favourite_set_ids(player.id)
    return Response(
        "\n".join([str(map_set_id) for map_set_id in favourite_set_ids]).encode(),
    )


@router.get("/web/osu-addfavourite.php")
async def osuAddFavourite(
    *,
    osu_client_authentication: Annotated[
        OsuClientAuthenticationService,
        Depends(api_dependencies.get_osu_client_authentication_service),
    ],
    username: str = Query(..., alias="u"),
    password_md5: str = Query(..., alias="h"),
    map_set_id: int = Query(..., alias="a"),
    favourites_service: Annotated[
        FavouritesService,
        Depends(api_dependencies.get_favourites_service),
    ],
) -> Response:
    player = await osu_client_authentication.authenticate_online_player(
        username=unquote(username),
        password_md5=password_md5,
    )
    if player is None:
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)

    result = await favourites_service.add_favourite(
        player_id=player.id,
        map_set_id=map_set_id,
    )
    if result is AddFavouriteResult.ALREADY_FAVOURITED:
        return Response(b"You've already favourited this beatmap!")

    return Response(b"Added favourite!")


@router.get("/web/lastfm.php")
async def lastFM(
    *,
    action: Literal["scrobble", "np"],
    beatmap_id_or_hidden_flag: str = Query(
        ...,
        description=(
            "This flag is normally a beatmap ID, but is also "
            "used as a hidden anticheat flag within osu!"
        ),
        alias="b",
    ),
    osu_client_authentication: Annotated[
        OsuClientAuthenticationService,
        Depends(api_dependencies.get_osu_client_authentication_service),
    ],
    username: str = Query(..., alias="us"),
    password_md5: str = Query(..., alias="ha"),
    client_integrity_service: Annotated[
        ClientIntegrityService,
        Depends(api_dependencies.get_client_integrity_service),
    ],
) -> Response:
    player = await osu_client_authentication.authenticate_online_player(
        username=unquote(username),
        password_md5=password_md5,
    )
    if player is None:
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)

    result = await client_integrity_service.handle_lastfm_flags(
        player=player,
        beatmap_id_or_hidden_flag=beatmap_id_or_hidden_flag,
    )
    if result is ClientIntegrityResult.STOP_SENDING:
        return Response(b"-3")

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


def format_direct_search_response(result: DirectSearchResult) -> bytes:
    assert result.beatmap_sets is not None
    response_lines = [str(result.result_count)]

    for beatmap_set in result.beatmap_sets:
        diffs_str = ",".join(
            [
                DIRECT_MAP_INFO_FMTSTR.format(
                    DifficultyRating=beatmap.difficulty_rating,
                    DiffName=beatmap.name,
                    CS=beatmap.cs,
                    OD=beatmap.od,
                    AR=beatmap.ar,
                    HP=beatmap.hp,
                    Mode=beatmap.mode,
                )
                for beatmap in beatmap_set.beatmaps
            ],
        )
        response_lines.append(
            DIRECT_SET_INFO_FMTSTR.format(
                Artist=beatmap_set.artist,
                Title=beatmap_set.title,
                Creator=beatmap_set.creator,
                RankedStatus=beatmap_set.ranked_status,
                LastUpdate=beatmap_set.last_update,
                SetID=beatmap_set.set_id,
                HasVideo=beatmap_set.has_video,
                diffs=diffs_str,
            ),
        )

    return "\n".join(response_lines).encode()


@router.get("/web/osu-search.php")
async def osuSearchHandler(
    *,
    osu_client_authentication: Annotated[
        OsuClientAuthenticationService,
        Depends(api_dependencies.get_osu_client_authentication_service),
    ],
    username: str = Query(..., alias="u"),
    password_md5: str = Query(..., alias="h"),
    ranked_status: int = Query(..., alias="r", ge=0, le=8),
    query: str = Query(..., alias="q"),
    mode: int = Query(..., alias="m", ge=-1, le=3),  # -1 for all
    page_num: int = Query(..., alias="p"),
    direct_search_service: Annotated[
        DirectSearchService,
        Depends(api_dependencies.get_direct_search_service),
    ],
) -> Response:
    if (
        await osu_client_authentication.authenticate_online_player(
            username=unquote(username),
            password_md5=password_md5,
        )
        is None
    ):
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)

    result = await direct_search_service.search(
        ranked_status=ranked_status,
        query=query,
        mode=mode,
        page_num=page_num,
    )
    if result.code is DirectSearchResultCode.MIRROR_ERROR:
        return Response(b"-1\nFailed to retrieve data from the beatmap mirror.")

    return Response(format_direct_search_response(result))


# TODO: video support (needs db change)
@router.get("/web/osu-search-set.php")
async def osuSearchSetHandler(
    *,
    osu_client_authentication: Annotated[
        OsuClientAuthenticationService,
        Depends(api_dependencies.get_osu_client_authentication_service),
    ],
    username: str = Query(..., alias="u"),
    password_md5: str = Query(..., alias="h"),
    map_set_id: int | None = Query(None, alias="s"),
    map_id: int | None = Query(None, alias="b"),
    checksum: str | None = Query(None, alias="c"),
    beatmap_set_service: Annotated[
        BeatmapSetService,
        Depends(api_dependencies.get_beatmap_set_service),
    ],
) -> Response:
    if (
        await osu_client_authentication.authenticate_online_player(
            username=unquote(username),
            password_md5=password_md5,
        )
        is None
    ):
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)

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
    *,
    osu_client_authentication: Annotated[
        OsuClientAuthenticationService,
        Depends(api_dependencies.get_osu_client_authentication_service),
    ],
    username: str = Query(..., alias="u"),
    password_md5: str = Query(..., alias="h"),
    mode: int = Query(..., alias="m", ge=0, le=3),
    score_id: int = Query(..., alias="c", min=0, max=9_223_372_036_854_775_807),
    replay_service: Annotated[
        ReplayService,
        Depends(api_dependencies.get_replay_service),
    ],
) -> Response:
    player = await osu_client_authentication.authenticate_online_player(
        username=unquote(username),
        password_md5=password_md5,
    )
    if player is None:
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)

    replay = await replay_service.fetch_replay_file(
        viewer_id=player.id,
        score_id=score_id,
    )
    if replay.code is ReplayResultCode.NOT_FOUND:
        return Response(b"", status_code=404)

    assert replay.path is not None
    return FileResponse(replay.path)


@router.get("/web/osu-rate.php")
async def osuRate(
    *,
    osu_client_authentication: Annotated[
        OsuClientAuthenticationService,
        Depends(api_dependencies.get_osu_client_authentication_service),
    ],
    username: str = Query(..., alias="u"),
    password_md5: str = Query(..., alias="p"),
    map_md5: str = Query(..., alias="c", min_length=32, max_length=32),
    rating: int | None = Query(None, alias="v", ge=1, le=10),
    beatmap_rating_service: Annotated[
        BeatmapRatingService,
        Depends(api_dependencies.get_beatmap_rating_service),
    ],
) -> Response:
    player = await osu_client_authentication.authenticate_online_player(
        username=unquote(username),
        password_md5=password_md5,
    )
    if player is None:
        return Response(b"auth fail", status_code=status.HTTP_401_UNAUTHORIZED)

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


def format_scores_response(leaderboard: BeatmapLeaderboardResult) -> bytes:
    assert leaderboard.ranked_status is not None
    assert leaderboard.beatmap_id is not None
    assert leaderboard.beatmap_set_id is not None
    assert leaderboard.beatmap_name is not None
    assert leaderboard.beatmap_rating is not None
    assert leaderboard.score_rows is not None

    response_lines: list[str] = [
        # NOTE: fa stands for featured artist (for the ones that may not know)
        # {ranked_status}|{serv_has_osz2}|{bid}|{bsid}|{len(scores)}|{fa_track_id}|{fa_license_text}
        f"{int(leaderboard.ranked_status)}|false|{leaderboard.beatmap_id}|{leaderboard.beatmap_set_id}|{len(leaderboard.score_rows)}|0|",
        # {offset}\n{beatmap_name}\n{rating}
        # TODO: server side beatmap offsets
        f"0\n{leaderboard.beatmap_name}\n{leaderboard.beatmap_rating}",
    ]

    if not leaderboard.score_rows:
        response_lines.extend(("", ""))  # no scores, no personal best
        return "\n".join(response_lines).encode()

    if leaderboard.personal_best_score_row is not None:
        assert leaderboard.personal_best_display_name is not None
        assert leaderboard.personal_best_user_id is not None
        response_lines.append(
            SCORE_LISTING_FMTSTR.format(
                **leaderboard.personal_best_score_row,
                name=leaderboard.personal_best_display_name,
                userid=leaderboard.personal_best_user_id,
                score=int(
                    round(leaderboard.personal_best_score_row["leaderboard_value"]),
                ),
                has_replay="1",
            ),
        )
    else:
        response_lines.append("")

    response_lines.extend(
        [
            SCORE_LISTING_FMTSTR.format(
                **score_row,
                score=int(round(score_row["leaderboard_value"])),
                has_replay="1",
                rank=idx + 1,
            )
            for idx, score_row in enumerate(leaderboard.score_rows)
        ],
    )

    return "\n".join(response_lines).encode()


@router.get("/web/osu-osz2-getscores.php")
async def getScores(
    *,
    osu_client_authentication: Annotated[
        OsuClientAuthenticationService,
        Depends(api_dependencies.get_osu_client_authentication_service),
    ],
    username: str = Query(..., alias="us"),
    password_md5: str = Query(..., alias="ha"),
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
    beatmap_leaderboard_service: Annotated[
        BeatmapLeaderboardService,
        Depends(api_dependencies.get_beatmap_leaderboard_service),
    ],
) -> Response:
    player = await osu_client_authentication.authenticate_online_player(
        username=unquote(username),
        password_md5=password_md5,
    )
    if player is None:
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)

    leaderboard = await beatmap_leaderboard_service.fetch_leaderboard(
        player=player,
        request=BeatmapLeaderboardRequest(
            requesting_from_editor_song_select=requesting_from_editor_song_select,
            leaderboard_type=leaderboard_type,
            map_md5=map_md5,
            map_filename=map_filename,
            mode_arg=mode_arg,
            map_set_id=map_set_id,
            mods_arg=mods_arg,
            aqn_files_found=aqn_files_found,
        ),
    )

    if leaderboard.code is BeatmapLeaderboardResultCode.NOT_SUBMITTED:
        return Response(b"-1|false")
    if leaderboard.code is BeatmapLeaderboardResultCode.NEEDS_UPDATE:
        return Response(b"1|false")
    if leaderboard.code is BeatmapLeaderboardResultCode.NO_LEADERBOARD:
        assert leaderboard.ranked_status is not None
        return Response(f"{int(leaderboard.ranked_status)}|false".encode())

    return Response(format_scores_response(leaderboard))


@router.post("/web/osu-comment.php")
async def osuComment(
    *,
    osu_client_authentication: Annotated[
        OsuClientAuthenticationService,
        Depends(api_dependencies.get_osu_client_authentication_service),
    ],
    username: str = Form(..., alias="u"),
    password_md5: str = Form(..., alias="p"),
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
    player = await osu_client_authentication.authenticate_online_player(
        username=unquote(username),
        password_md5=password_md5,
    )
    if player is None:
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)

    if action == "get":
        # client is requesting all comments
        comments = await comments_service.fetch_relevant_to_replay_for_player(
            player=player,
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

        return Response("\n".join(ret).encode())

    elif action == "post":
        # client is submitting a new comment

        # validate all required params are provided
        assert target is not None
        assert start_time is not None
        assert comment is not None

        await comments_service.create_comment_for_player(
            player=player,
            target=target,
            map_set_id=map_set_id,
            map_id=map_id,
            score_id=score_id,
            start_time=start_time,
            comment=comment,
            colour=colour,
        )

    return Response(b"")  # empty resp is fine


@router.get("/web/osu-markasread.php")
async def osuMarkAsRead(
    *,
    osu_client_authentication: Annotated[
        OsuClientAuthenticationService,
        Depends(api_dependencies.get_osu_client_authentication_service),
    ],
    username: str = Query(..., alias="u"),
    password_md5: str = Query(..., alias="h"),
    channel: str = Query(..., min_length=0, max_length=32),
    mail_read_service: Annotated[
        MailReadService,
        Depends(api_dependencies.get_mail_read_service),
    ],
) -> Response:
    player = await osu_client_authentication.authenticate_online_player(
        username=unquote(username),
        password_md5=password_md5,
    )
    if player is None:
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)

    await mail_read_service.mark_channel_as_read(
        player=player,
        channel=channel,
    )

    return Response(b"")


@router.get("/web/osu-getseasonal.php")
async def osuSeasonal() -> Response:
    return ORJSONResponse(app.settings.SEASONAL_BGS)


@router.get("/web/bancho_connect.php")
async def banchoConnect(
    # NOTE: this is disabled as this endpoint can be called
    #       before a player has been granted a session
    # TODO: authenticate this endpoint when the client reliably has a session.
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
    result = await account_registration_service.check_or_register(
        username=username,
        email=email,
        password=pw_plaintext,
        should_create_account=check == 0,
        request_headers=request.headers,
    )

    if result.code is AccountRegistrationResultCode.MISSING_REQUIRED_PARAMS:
        return Response(
            content=b"Missing required params",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if result.code is AccountRegistrationResultCode.INGAME_REGISTRATION_DISABLED:
        return ORJSONResponse(
            content=INGAME_REGISTRATION_DISALLOWED_ERROR,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if result.code is AccountRegistrationResultCode.VALIDATION_FAILED:
        assert result.errors is not None
        # we have errors to send back, send them back delimited by newlines.
        formatted_errors = {k: ["\n".join(v)] for k, v in result.errors.items()}
        errors_full = {"form_error": {"user": formatted_errors}}
        return ORJSONResponse(
            content=errors_full,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return Response(content=b"ok")  # success


@router.post("/difficulty-rating")
async def difficultyRatingHandler(request: Request) -> Response:
    return RedirectResponse(
        url=f"https://osu.ppy.sh{request['path']}",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )
