""" osu: handle web connections from osu! """
import copy
import hashlib
import ipaddress
import random
import secrets
import time
from base64 import b64decode
from collections import defaultdict
from enum import IntEnum
from enum import unique
from pathlib import Path as SystemPath
from typing import AsyncIterator
from typing import Literal
from typing import Mapping
from typing import Optional
from typing import TYPE_CHECKING
from urllib.parse import unquote
from urllib.parse import unquote_plus

import bcrypt
import databases.core
import orjson
import sqlalchemy
from cmyui.logging import Ansi
from cmyui.logging import log
from cmyui.logging import printc
from cmyui.web import ratelimit
from fastapi import APIRouter
from fastapi import Depends
from fastapi import status
from fastapi.datastructures import UploadFile
from fastapi.param_functions import File
from fastapi.param_functions import Form
from fastapi.param_functions import Header
from fastapi.param_functions import Path
from fastapi.param_functions import Query
from fastapi.requests import Request
from fastapi.responses import FileResponse
from fastapi.responses import ORJSONResponse
from fastapi.responses import Response
from py3rijndael import Pkcs7Padding
from py3rijndael import RijndaelCbc
from pydantic import BaseModel
from sqlalchemy.sql.expression import insert
from sqlalchemy.sql.expression import join
from sqlalchemy.sql.expression import select
from sqlalchemy.sql.expression import update
from sqlalchemy.sql.functions import func
from starlette.responses import RedirectResponse

import app.db_models
import app.misc.utils
import app.services
import app.settings
import packets
from app.constants import regexes
from app.constants.clientflags import ClientFlags
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.misc.utils import escape_enum
from app.misc.utils import pymysql_encode
from app.objects import glob
from app.objects.beatmap import Beatmap
from app.objects.beatmap import ensure_local_osu_file
from app.objects.beatmap import RankedStatus
from app.objects.player import Privileges
from app.objects.score import Grade
from app.objects.score import Score
from app.objects.score import SubmissionStatus

if TYPE_CHECKING:
    pass

AVATARS_PATH = SystemPath.cwd() / ".data/avatars"
BEATMAPS_PATH = SystemPath.cwd() / ".data/osu"
REPLAYS_PATH = SystemPath.cwd() / ".data/osr"
SCREENSHOTS_PATH = SystemPath.cwd() / ".data/ss"

router = APIRouter(prefix="/osu", tags=["osu! web API"])


async def acquire_db_conn() -> AsyncIterator[databases.core.Connection]:
    """Decorator to acquire a database connection for a handler."""
    async with app.services.database.connection() as conn:
        yield conn


""" /web/ handlers """

# TODO
# POST /web/osu-session.php
# POST /web/osu-osz2-bmsubmit-post.php
# POST /web/osu-osz2-bmsubmit-upload.php
# GET /web/osu-osz2-bmsubmit-getid.php
# GET /web/osu-get-beatmap-topic.php


@router.post("/web/osu-error.php")
async def osuError(
    username: Optional[str] = Form(None, alias="u"),
    pw_md5: Optional[str] = Form(None, alias="h"),
    user_id: int = Form(..., alias="i", ge=3, le=2_147_483_647),
    osu_mode: int = Form(..., alias="osumode", ge=0, le=23),
    game_mode: int = Form(..., alias="gamemode", ge=0, le=3),
    game_time: int = Form(..., alias="gametime", ge=0),
    audio_time: int = Form(..., alias="audiotime"),
    culture: str = Form(..., alias="culture"),
    map_id: int = Form(..., alias="beatmap_id", ge=0, le=2_147_483_647),
    map_md5: str = Form(..., alias="beatmap_checksum", min_length=32, max_length=32),
    exception: str = Form(..., alias="exception"),
    feedback: str = Form(..., alias="feedback"),
    stacktrace: str = Form(..., alias="stacktrace"),
    soft: bool = Form(..., alias="soft"),
    map_count: int = Form(..., alias="beatmap_count", ge=0),
    compatibility: bool = Form(..., alias="compatibility"),
    ram: int = Form(..., alias="ram"),
    osu_ver: str = Form(..., alias="version"),
    exe_hash: str = Form(..., alias="exehash"),
    config: str = Form(..., alias="config"),
    screenshot_file: Optional[UploadFile] = File(None, alias="ss"),  # octet stream?
):
    """Handle an error submitted from the osu! client."""
    if not glob.app.debug:
        # only handle osu-error in debug mode
        return

    if username and pw_md5:
        if not (
            player := await glob.players.from_login(
                name=unquote(username),
                pw_md5=pw_md5,
            )
        ):
            # player login incorrect
            await app.services.log_strange_occurrence("osu-error auth failed")
            player = None
    else:
        player = None

    err_desc = f"{feedback} ({exception})"
    log(f'{player or "Offline user"} sent osu-error: {err_desc}', Ansi.LCYAN)

    # NOTE: this stacktrace can be a LOT of data
    if glob.config.debug and len(stacktrace) < 2000:
        printc(stacktrace[:-2], Ansi.LMAGENTA)

    # TODO: save error in db?


@router.post("/web/osu-screenshot.php")
async def osuScreenshot(
    username: str = Form(..., alias="u"),
    pw_md5: str = Form(..., alias="p"),
    endpoint_version: int = Form(..., alias="v"),
    screenshot_data: bytes = File(..., alias="ss"),
):
    if not (
        player := await glob.players.from_login(
            name=unquote(username),
            pw_md5=pw_md5,
        )
    ):
        # player login incorrect
        return

    ss_data_view = memoryview(screenshot_data).toreadonly()

    # png sizes: 1080p: ~300-800kB | 4k: ~1-2mB
    if len(ss_data_view) > (4 * 1024 * 1024):
        return Response(
            content=b"Screenshot file too large.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if endpoint_version != 1:
        await app.services.log_strange_occurrence(
            f"Incorrect endpoint version (/web/osu-screenshot.php v{endpoint_version})",
        )

    if ss_data_view[:4] == b"\xff\xd8\xff\xe0" and ss_data_view[6:11] == b"JFIF\x00":
        extension = "jpeg"
    elif (
        ss_data_view[:8] == b"\x89PNG\r\n\x1a\n"
        and ss_data_view[-8] == b"\x49END\xae\x42\x60\x82"
    ):
        extension = "png"
    else:
        return Response(
            content=b"Invalid file type.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    while True:
        filename = f"{secrets.token_urlsafe(6)}.{extension}"
        ss_file = SCREENSHOTS_PATH / filename
        if not ss_file.exists():
            break

    with ss_file.open("wb") as f:
        f.write(ss_data_view)

    log(f"{player} uploaded {filename}.")
    return filename.encode()


@router.get("/web/osu-getfriends.php")
async def osuGetFriends(
    username: str = Form(..., alias="u"),
    pw_md5: str = Form(..., alias="h"),
):
    if not (
        player := await glob.players.from_login(
            name=unquote(username),
            pw_md5=pw_md5,
        )
    ):
        # player login incorrect
        return

    return "\n".join(map(str, player.friends)).encode()


_gulag_osuapi_status_map = {0: 0, 2: 1, 3: 2, 4: 3, 5: 4}


def gulag_to_osuapi_status(s: int) -> int:
    return _gulag_osuapi_status_map[s]


class OsuBeatmapRequestForm(BaseModel):
    Filenames: list[str]
    Ids: list[int]


@router.post("/web/osu-getbeatmapinfo.php")
async def osuGetBeatmapInfo(
    form_data: OsuBeatmapRequestForm,
    username: str = Form(..., alias="u"),
    pw_md5: str = Form(..., alias="h"),
    db_conn: databases.core.Connection = Depends(acquire_db_conn),
):
    if not (
        player := await glob.players.from_login(
            name=unquote(username),
            pw_md5=pw_md5,
        )
    ):
        # player login incorrect
        return

    num_requests = len(form_data.Filenames) + len(form_data.Ids)
    log(f"{player} requested info for {num_requests} maps.", Ansi.LCYAN)

    ret = []

    for idx, map_filename in enumerate(form_data.Filenames):
        # try getting the map from sql
        row = await db_conn.fetch_one(
            select(
                [
                    app.db_models.maps.c.id,
                    app.db_models.maps.c.set_id,
                    app.db_models.maps.c.status,
                    app.db_models.maps.c.md5,
                ],
            ).where(app.db_models.maps.c.filename == map_filename),
        )

        # convert from gulag -> osu!api status
        row["status"] = gulag_to_osuapi_status(row["status"])

        # try to get the user's grades on the map osu!
        # only allows us to send back one per gamemode,
        # so we'll just send back relax for the time being..
        # XXX: perhaps user-customizable in the future?
        grades = ["N", "N", "N", "N"]

        score_res = await db_conn.fetch_all(
            select(
                [app.db_models.scores_rx.c.grade, app.db_models.scores_rx.c.mode],
            ).where(
                sqlalchemy.and_(
                    app.db_models.scores_rx.c.map_md5 == row["md5"],
                    app.db_models.scores_rx.c.userid == player.id,
                    app.db_models.scores_rx.c.status == 2,
                ),
            ),
        )

        for score in score_res:
            grades[score["mode"]] = score["grade"]

        ret.append(
            "{i}|{id}|{set_id}|{md5}|{status}|{grades}".format(
                **row, i=idx, grades="|".join(grades)
            ),
        )

    if form_data.Ids:  # still have yet to see this used
        await app.services.log_strange_occurrence(
            f"{player} requested map(s) info by id ({form_data.Ids})",
        )

    return "\n".join(ret).encode()


@router.get("/web/osu-getfavourites.php")
async def osuGetFavourites(
    username: str = Query(..., alias="u"),
    pw_md5: str = Query(..., alias="h"),
    db_conn: databases.core.Connection = Depends(acquire_db_conn),
):
    if not (
        player := await glob.players.from_login(
            name=unquote(username),
            pw_md5=pw_md5,
        )
    ):
        # player login incorrect
        return

    favourites = await db_conn.fetch_all(
        app.db_models.favourites.select(app.db_models.favourites.c.setid).where(
            app.db_models.favourites.c.userid == player.id,
        ),
    )

    return "\n".join([row["setid"] for row in favourites]).encode()


@router.get("/web/osu-addfavourite.php")
async def osuAddFavourite(
    username: str = Query(..., alias="u"),
    pw_md5: str = Query(..., alias="h"),
    map_set_id: int = Query(..., alias="a"),
    db_conn: databases.core.Connection = Depends(acquire_db_conn),
):
    if not (
        player := await glob.players.from_login(
            name=unquote(username),
            pw_md5=pw_md5,
        )
    ):
        # player login incorrect
        return

    # check if they already have this favourited.
    res = await db_conn.fetch_one(
        app.db_models.favourites.select().where(
            sqlalchemy.and_(
                app.db_models.favourites.c.userid == player.id,
                app.db_models.favourites.c.setid == map_set_id,
            ),
        ),
    )

    if res:
        return b"You've already favourited this beatmap!"

    # add favourite
    await db_conn.execute(
        insert(app.db_models.favourites).values(id=player.id, setid=map_set_id),
    )


@router.get("/web/lastfm.php")
async def lastFM(
    action: Literal["scrobble", "np"],
    beatmap_id_or_hidden_flag: str = Query(
        ...,
        description=(
            "This flag is normally a beatmap ID, but is also "
            "used as a hidden anticheat flag within osu!"
        ),
    ),
    username: str = Query(..., alias="us"),
    pw_md5: str = Query(..., alias="ha"),
):
    if not (
        player := await glob.players.from_login(
            name=unquote(username),
            pw_md5=pw_md5,
        )
    ):
        # player login incorrect
        return

    if beatmap_id_or_hidden_flag[0] != "a":
        # not anticheat related, tell the
        # client not to send any more for now.
        return b"-3"

    flags = ClientFlags(int(beatmap_id_or_hidden_flag[1:]))

    if flags & (ClientFlags.HQ_ASSEMBLY | ClientFlags.HQ_FILE):
        # Player is currently running hq!osu; could possibly
        # be a separate client, buuuut prooobably not lol.

        await player.restrict(admin=glob.bot, reason=f"hq!osu running ({flags})")
        return b"-3"

    if flags & ClientFlags.REGISTRY_EDITS:
        # Player has registry edits left from
        # hq!osu's multiaccounting tool. This
        # does not necessarily mean they are
        # using it now, but they have in the past.

        if random.randrange(32) == 0:
            # Random chance (1/32) for a ban.
            await player.restrict(admin=glob.bot, reason="hq!osu relife 1/32")
            return b"-3"

        # TODO: make a tool to remove the flags & send this as a dm.
        #       also add to db so they never are restricted on first one.
        player.enqueue(
            packets.notification(
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

        return b"-3"

    """ These checks only worked for ~5 hours from release. rumoi's quick!
    if flags & (ClientFlags.libeay32Library | ClientFlags.aqnMenuSample):
        # AQN has been detected in the client, either
        # through the 'libeay32.dll' library being found
        # onboard, or from the menu sound being played in
        # the AQN menu while being in an inappropriate menu
        # for the context of the sound effect.
        pass
    """


# gulag supports both cheesegull mirrors & chimu.moe.
# chimu.moe handles things a bit differently than cheesegull,
# and has some extra features we'll eventually use more of.
USING_CHIMU = "chimu.moe" in glob.config.mirror

DIRECT_SET_INFO_FMTSTR = (
    "{{{setid_spelling}}}.osz|{{Artist}}|{{Title}}|{{Creator}}|"
    "{{RankedStatus}}|10.0|{{LastUpdate}}|{{{setid_spelling}}}|"
    "0|{{HasVideo}}|0|0|0|{{diffs}}"  # 0s are threadid, has_story,
    # filesize, filesize_novid.
).format(setid_spelling="SetId" if USING_CHIMU else "SetID")

DIRECT_MAP_INFO_FMTSTR = (
    "[{DifficultyRating:.2f}⭐] {DiffName} "
    "{{cs: {CS} / od: {OD} / ar: {AR} / hp: {HP}}}@{Mode}"
)


@router.get("/web/osu-search.php")
async def osuSearchHandler(
    username: str = Query(..., alias="u"),
    pw_md5: str = Query(..., alias="h"),
    ranked_status: int = Query(..., alias="r", ge=0, le=8),
    query: str = Query(..., alias="q"),
    mode: int = Query(..., alias="m", ge=-1, le=3),  # -1 for all
    page_num: int = Query(..., alias="p"),
):
    if not (
        player := await glob.players.from_login(
            name=unquote(username),
            pw_md5=pw_md5,
        )
    ):
        # player login incorrect
        return

    if USING_CHIMU:
        search_url = f"{glob.config.mirror}/search"
    else:
        search_url = f"{glob.config.mirror}/api/search"

    params: dict[str, object] = {"amount": 100, "offset": page_num * 100}

    # eventually we could try supporting these,
    # but it mostly depends on the mirror.
    if query not in ("Newest", "Top+Rated", "Most+Played"):
        params["query"] = query

    if mode != -1:  # -1 for all
        params["mode"] = mode

    if ranked_status != 4:  # 4 for all
        # convert to osu!api status
        status = RankedStatus.from_osudirect(ranked_status)
        params["status"] = status.osu_api

    async with app.services.http_session.get(search_url, params=params) as resp:
        if not resp:
            stacktrace = app.misc.utils.get_appropriate_stacktrace()
            await app.services.log_strange_occurrence(stacktrace)

        if USING_CHIMU:  # error handling varies
            if resp.status == 404:
                return b"0"  # no maps found
            elif resp.status >= 500:  # chimu server error (happens a lot :/)
                return b"-1\nFailed to retrieve data from the beatmap mirror."
            elif resp.status != 200:
                stacktrace = app.misc.utils.get_appropriate_stacktrace()
                await app.services.log_strange_occurrence(stacktrace)
                return b"-1\nFailed to retrieve data from the beatmap mirror."
        else:  # cheesegull
            if resp.status != 200:
                return b"-1\nFailed to retrieve data from the beatmap mirror."

        result = await resp.json()

        if USING_CHIMU:
            if result["code"] != 0:
                stacktrace = app.misc.utils.get_appropriate_stacktrace()
                await app.services.log_strange_occurrence(stacktrace)
                return b"-1\nFailed to retrieve data from the beatmap mirror."
            result = result["data"]

    # 100 matches, so the client knows there are more to get
    ret = [f"{'101' if len(result) == 100 else len(result)}"]

    for bmap in result:
        if bmap["ChildrenBeatmaps"] is None:
            continue

        if USING_CHIMU:
            bmap["HasVideo"] = int(bmap["HasVideo"])
        else:
            # cheesegull doesn't support vids
            bmap["HasVideo"] = "0"

        diff_sorted_maps = sorted(
            bmap["ChildrenBeatmaps"],
            key=lambda m: m["DifficultyRating"],
        )
        diffs_str = ",".join(
            [DIRECT_MAP_INFO_FMTSTR.format(**row) for row in diff_sorted_maps],
        )

        ret.append(DIRECT_SET_INFO_FMTSTR.format(**bmap, diffs=diffs_str))

    return "\n".join(ret).encode()


# TODO: video support (needs db change)
@router.get("/web/osu-search-set.php")
async def osuSearchSetHandler(
    username: str = Query(..., alias="u"),
    pw_md5: str = Query(..., alias="h"),
    map_set_id: Optional[int] = Query(None, alias="s"),
    map_id: Optional[int] = Query(None, alias="b"),
    db_conn: databases.core.Connection = Depends(acquire_db_conn),
):
    if not (
        player := await glob.players.from_login(
            name=unquote(username),
            pw_md5=pw_md5,
        )
    ):
        # player login incorrect
        return

    # TODO: refactor this to use the new internal bmap(set) api

    # Since we only need set-specific data, we can basically
    # just do same same query with either bid or bsid.

    if map_set_id is not None:
        # this is just a normal request
        k, v = (app.db_models.maps.c.set_id, map_set_id)
    elif map_id is not None:
        k, v = (app.db_models.maps.c.id, map_id)
    else:
        return  # invalid args

    # Get all set data.
    bmapset = await db_conn.fetch_one(
        select(
            [
                app.db_models.maps.c.set_id,
                app.db_models.maps.c.artist,
                app.db_models.maps.c.title,
                app.db_models.maps.c.status,
                app.db_models.maps.c.creator,
                app.db_models.maps.c.last_update,
            ],
        )
        .where(k == v)
        .distinct(),
    )

    if not bmapset:
        # TODO: get from osu!
        return

    return (
        (
            "{set_id}.osz|{artist}|{title}|{creator}|"
            "{status}|10.0|{last_update}|{set_id}|"  # TODO: rating
            "0|0|0|0|0"
        )
        .format(**bmapset)
        .encode()
    )
    # 0s are threadid, has_vid, has_story, filesize, filesize_novid


def chart_entry(name: str, before: Optional[object], after: object) -> str:
    return f'{name}Before:{before or ""}|{name}After:{after}'


@router.post("/web/osu-submit-modular-selector.php")
async def osuSubmitModularSelector(
    # TODO: figure out object types/names
    # TODO: do ft & st contain pauses?
    exited_out: bool = Query(..., alias="x"),
    fail_time: int = Query(..., alias="ft"),
    score_data_b64: str = Query(..., alias="score"),
    visual_settings_b64: str = Query(..., alias="fs"),
    bmk: str = Query(...),
    iv_b64: str = Query(...),
    unique_id: str = Query(..., alias="c1"),  # TODO: more validaton
    score_time: int = Query(..., alias="st"),  # TODO: is this real name?
    pw_md5: str = Query(..., alias="pass"),
    osu_ver: str = Query(..., alias="osuver"),  # TODO: regex
    client_hash_b64: str = Query(..., alias="s"),
    # TODO: do these need to be Optional?
    # TODO: validate this is actually what it is
    fl_cheat_screenshot: bytes = File(..., alias="i"),
    # TODO: how am i gonna ban them?
    replay_data: bytes = File(..., alias="score"),
    db_conn: databases.core.Connection = Depends(acquire_db_conn),
):
    # attempt to decrypt score data
    aes = RijndaelCbc(
        key=f"osu!-scoreburgr---------{osu_ver}".encode(),
        iv=b64decode(iv_b64),
        padding=Pkcs7Padding(32),
        block_size=32,
    )

    # score data is delimited by colons (:).
    score_data = aes.decrypt(b64decode(score_data_b64)).decode().split(":")

    # fetch map & player

    bmap_md5 = score_data[0]
    if not (bmap := await Beatmap.from_md5(bmap_md5)):
        # Map does not exist, most likely unsubmitted.
        return b"error: beatmap"

    username = score_data[1].rstrip()  # rstrip 1 space if client has supporter
    if not (player := await glob.players.from_login(username, pw_md5)):
        # Player is not online, return nothing so that their
        # client will retry submission when they log in.
        return

    # parse the score from the remaining data
    score = await Score.from_submission(score_data[2:])

    # attach bmap & player
    score.bmap = bmap
    score.player = player

    # all data read from submission.
    # now we can calculate things based on our data.
    score.acc = score.calc_accuracy()

    if score.bmap:
        osu_file_path = BEATMAPS_PATH / f"{score.bmap.id}.osu"
        if await ensure_local_osu_file(osu_file_path, score.bmap.id, score.bmap.md5):
            score.pp, score.sr = score.calc_diff(osu_file_path)

            if score.passed:
                await score.calc_status()

                if score.bmap.status != RankedStatus.Pending:
                    score.rank = await score.calc_lb_placement()
            else:
                score.status = SubmissionStatus.FAILED
    else:
        score.pp = score.sr = 0.0
        if score.passed:
            score.status = SubmissionStatus.SUBMITTED
        else:
            score.status = SubmissionStatus.FAILED

    # we should update their activity no matter
    # what the result of the score submission is.
    await score.player.update_latest_activity()

    # attempt to update their stats if their
    # gm/gm-affecting-mods change at all.
    if score.mode != score.player.status.mode:
        score.player.status.mods = score.mods
        score.player.status.mode = score.mode

        if not score.player.restricted:
            glob.players.enqueue(packets.user_stats(score.player))

    scores_table = score.mode.scores_table
    mode_vn = score.mode.as_vanilla

    # Check for score duplicates
    alchemy_table = getattr(app.db_models, scores_table)
    duplicate_res = await db_conn.fetch_one(
        alchemy_table.select().where(
            alchemy_table.c.online_checksum == score.online_checksum,
        ),
    )

    if duplicate_res:
        log(f"{score.player} submitted a duplicate score.", Ansi.LYELLOW)
        return b"error: no"

    time_elapsed = score_time if score.passed else fail_time

    score.time_elapsed = int(time_elapsed)

    if fl_cheat_screenshot:
        stacktrace = app.misc.utils.get_appropriate_stacktrace()
        await app.services.log_strange_occurrence(stacktrace)

    if (  # check for pp caps on ranked & approved maps for appropriate players.
        score.bmap.awards_ranked_pp
        and not (score.player.priv & Privileges.WHITELISTED or score.player.restricted)
    ):
        # Get the PP cap for the current context.
        pp_cap = glob.config.autoban_pp[score.mode][score.mods & Mods.FLASHLIGHT != 0]

        if score.pp > pp_cap:
            await score.player.restrict(
                admin=glob.bot,
                reason=f"[{score.mode!r} {score.mods!r}] autoban @ {score.pp:.2f}pp",
            )

    """ Score submission checks completed; submit the score. """

    if glob.datadog:
        glob.datadog.increment("gulag.submitted_scores")

    if score.status == SubmissionStatus.BEST:
        if glob.datadog:
            glob.datadog.increment("gulag.submitted_scores_best")

        if score.bmap.has_leaderboard:
            if (
                score.mode < GameMode.RELAX_OSU
                and score.bmap.status == RankedStatus.Loved
            ):
                # use score for vanilla loved only
                performance = f"{score.score:,} score"
            else:
                performance = f"{score.pp:,.2f}pp"

            score.player.enqueue(
                packets.notification(f"You achieved #{score.rank}! ({performance})"),
            )

            if score.rank == 1 and not score.player.restricted:
                # this is the new #1, post the play to #announce.
                announce_chan = glob.channels["#announce"]

                # Announce the user's #1 score.
                # TODO: truncate artist/title/version to fit on screen
                ann = [
                    f"\x01ACTION achieved #1 on {score.bmap.embed}",
                    f"with {score.acc:.2f}% for {performance}.",
                ]

                if score.mods:
                    ann.insert(1, f"+{score.mods!r}")

                scoring_metric = "pp" if score.mode >= GameMode.RELAX_OSU else "score"

                # If there was previously a score on the map, add old #1.
                join_table = join(
                    alchemy_table,
                    app.db_models.users,
                    app.db_models.users.c.id == alchemy_table.c.userid,
                )
                prev_n1 = await db_conn.fetch_one(
                    select([app.db_models.users.c.id, app.db_models.users.c.name])
                    .select_from(join_table)
                    .where(
                        sqlalchemy.and_(
                            alchemy_table.c.map_md5 == score.bmap.md5,
                            alchemy_table.c.mode == mode_vn,
                            alchemy_table.c.status == 2,
                            app.db_models.users.c.priv & 1,
                        ),
                    )
                    .order_by(getattr(alchemy_table.c, scoring_metric).desc())
                    .limit(1),
                )

                if prev_n1:
                    if score.player.id != prev_n1["id"]:
                        ann.append(
                            f"(Previous #1: [https://{glob.config.domain}/u/"
                            f"{prev_n1['id']} {prev_n1['name']}])",
                        )

                announce_chan.send(" ".join(ann), sender=score.player, to_self=True)

        # this score is our best score.
        # update any preexisting personal best
        # records with SubmissionStatus.SUBMITTED.
        await db_conn.execute(
            alchemy_table.update()
            .values(status=SubmissionStatus.SUBMITTED)
            .where(
                sqlalchemy.and_(
                    alchemy_table.c.userid == score.player.id,
                    alchemy_table.c.map_md5 == score.bmap.md5,
                    alchemy_table.c.mode == mode_vn,
                ),
            ),
        )

    score.id = await db_conn.execute(
        insert(alchemy_table)
        .values(
            id=None,
            map_md5=score.bmap.md5,
            score=score.score,
            pp=score.pp,
            acc=score.acc,
            max_combo=score.max_combo,
            mods=score.mods,
            n300=score.n300,
            n100=score.n100,
            n50=score.n50,
            nmiss=score.nmiss,
            ngeki=score.ngeki,
            nkatu=score.nkatu,
            grade=score.grade.name,
            status=score.status,
            mode_vn=mode_vn,
            play_time=score.play_time,
            time_elapsed=score.time_elapsed,
            client_flags=score.client_flags,
            userid=score.player.id,
            perfect=score.perfect,
            online_checksum=score.online_checksum,
        )
        .returning(alchemy_table.c.id),
    )

    if score.passed:
        # All submitted plays should have a replay.
        # If not, they may be using a score submitter.
        if len(replay_data) < 24 and not score.player.restricted:
            log(f"{score.player} submitted a score without a replay!", Ansi.LRED)
            await score.player.restrict(
                admin=glob.bot,
                reason="submitted score with no replay",
            )
        else:
            # TODO: the replay is currently sent from the osu!
            # client compressed with LZMA; this compression can
            # be improved pretty decently by serializing it
            # manually, so we'll probably do that in the future.
            replay_file = REPLAYS_PATH / f"{score.id}.osr"
            replay_file.write_bytes(replay_data)

    """ Update the user's & beatmap's stats """

    # get the current stats, and take a
    # shallow copy for the response charts.
    stats = score.player.gm_stats
    prev_stats = copy.copy(stats)

    # stuff update for all submitted scores
    stats.playtime += score.time_elapsed // 1000
    stats.plays += 1
    stats.tscore += score.score

    stats_query_values: dict[str, object] = {
        "plays": stats.plays,
        "playtime": stats.playtime,
        "tscore": stats.tscore,
    }

    if score.passed and score.bmap.has_leaderboard:
        # player passed & map is ranked, approved, or loved.

        if score.max_combo > stats.max_combo:
            stats.max_combo = score.max_combo
            stats_query_values["max_combo"] = stats.max_combo

        if score.bmap.awards_ranked_pp and score.status == SubmissionStatus.BEST:
            # map is ranked or approved, and it's our (new)
            # best score on the map. update the player's
            # ranked score, grades, pp, acc and global rank.

            additional_rscore = score.score
            if score.prev_best:
                # we previously had a score, so remove
                # it's score from our ranked score.
                additional_rscore -= score.prev_best.score

                if score.grade != score.prev_best.grade:
                    if score.grade >= Grade.A:
                        stats.grades[score.grade] += 1
                        grade_col = format(score.grade, "stats_column")
                        stats_query_values[grade_col] = stats.grades[score.grade]

                    if score.prev_best.grade >= Grade.A:
                        stats.grades[score.prev_best.grade] -= 1
                        grade_col = format(score.prev_best.grade, "stats_column")
                        stats_query_values[grade_col] = stats.grades[
                            score.prev_best.grade
                        ]
            else:
                # this is our first submitted score on the map
                if score.grade >= Grade.A:
                    stats.grades[score.grade] += 1
                    grade_col = format(score.grade, "stats_column")
                    stats_query_values[grade_col] = stats.grades[score.grade]

            stats.rscore += additional_rscore
            stats_query_values["rscore"] = stats.rscore

            # fetch scores sorted by pp for total acc/pp calc
            # NOTE: we select all plays (and not just top100)
            # because bonus pp counts the total amount of ranked
            # scores. i'm aware this scales horribly and it'll
            # likely be split into two queries in the future.
            plays_table = join(
                app.db_models.maps,
                alchemy_table,
                alchemy_table.c.map_md5 == app.db_models.maps.c.md5,
            )

            rows = await db_conn.fetch_all(
                select([alchemy_table.pp, alchemy_table.acc])
                .select_from(plays_table)
                .where(
                    sqlalchemy.and_(
                        alchemy_table.c.userid == score.player.id,
                        alchemy_table.c.mode == mode_vn,
                        alchemy_table.c.status == 2,
                        app.db_models.maps.c.status in (2, 3),
                    ),
                )
                .order_by(alchemy_table.pp.desc()),
            )

            total_scores = len(rows)
            top_100_pp = rows[:100]

            # calculate new total weighted accuracy
            weighted_acc = sum(
                [row["acc"] * 0.95 ** i for i, row in enumerate(top_100_pp)],
            )
            bonus_acc = 100.0 / (20 * (1 - 0.95 ** total_scores))
            stats.acc = (weighted_acc * bonus_acc) / 100

            # add acc to query
            stats_query_values["acc"] = stats.acc

            # calculate new total weighted pp
            weighted_pp = sum(
                [row.pp * 0.95 ** i for i, row in enumerate(top_100_pp)],
            )
            bonus_pp = 416.6667 * (1 - 0.95 ** total_scores)
            stats.pp = round(weighted_pp + bonus_pp)

            # add pp to query
            stats_query_values["pp"] = stats.pp

            # update rank
            stats.rank = await score.player.update_rank(score.mode)

    # send any stat changes to sql, and other players
    await db_conn.execute(
        update(app.db_models.stats, values=stats_query_values).where(
            sqlalchemy.and_(
                app.db_models.stats.c.userid == score.player.id,
                app.db_models.stats.c.mode == score.mode.value,
            ),
        ),
    )
    glob.players.enqueue(packets.user_stats(score.player))

    if not score.player.restricted:
        # update beatmap with new stats
        score.bmap.plays += 1
        if score.passed:
            score.bmap.passes += 1

        await db_conn.execute(
            app.db_models.maps.update()
            .values(
                plays=score.bmap.plays,
                passes=score.bmap.passes,
            )
            .where(app.db_models.maps.c.md5 == score.bmap.md5),
        )

    # update their recent score
    score.player.recent_scores[score.mode] = score
    if "recent_score" in score.player.__dict__:
        del score.player.recent_score  # wipe cached_property

    """ score submission charts """

    if not score.passed or score.mode >= GameMode.RELAX_OSU:
        # charts & achievements won't be shown ingame.
        ret = b"error: no"

    else:
        # construct and send achievements & ranking charts to the client
        if score.bmap.awards_ranked_pp and not score.player.restricted:
            achievements = []
            for ach in glob.achievements:
                if ach in score.player.achievements:
                    # player already has this achievement.
                    continue

                if ach.cond(score, mode_vn):
                    await score.player.unlock_achievement(ach)
                    achievements.append(ach)

            achievements_str = "/".join(map(repr, achievements))
        else:
            achievements_str = ""

        # create score submission charts for osu! client to display

        if score.prev_best:
            beatmap_ranking_chart_entries = (
                chart_entry("rank", score.prev_best.rank, score.rank),
                chart_entry("rankedScore", score.prev_best.score, score.score),
                chart_entry("totalScore", score.prev_best.score, score.score),
                chart_entry("maxCombo", score.prev_best.max_combo, score.max_combo),
                chart_entry(
                    "accuracy",
                    f"{score.prev_best.acc:.2f}",
                    f"{score.acc:.2f}",
                ),
                chart_entry("pp", score.prev_best.pp, score.pp),
            )

            overall_ranking_chart_entries = (
                chart_entry("rank", prev_stats.rank, stats.rank),
                chart_entry("rankedScore", prev_stats.rscore, stats.rscore),
                chart_entry("totalScore", prev_stats.tscore, stats.tscore),
                chart_entry("maxCombo", prev_stats.max_combo, stats.max_combo),
                chart_entry("accuracy", f"{prev_stats.acc:.2f}", f"{stats.acc:.2f}"),
                chart_entry("pp", prev_stats.pp, stats.pp),
            )
        else:
            # no previous best score
            beatmap_ranking_chart_entries = (
                chart_entry("rank", None, score.rank),
                chart_entry("rankedScore", None, score.score),
                chart_entry("totalScore", None, score.score),
                chart_entry("maxCombo", None, score.max_combo),
                chart_entry("accuracy", None, f"{score.acc:.2f}"),
                chart_entry("pp", None, score.pp),
            )

            overall_ranking_chart_entries = (
                chart_entry("rank", None, stats.rank),
                chart_entry("rankedScore", None, stats.rscore),
                chart_entry("totalScore", None, stats.tscore),
                chart_entry("maxCombo", None, stats.max_combo),
                chart_entry("accuracy", None, f"{stats.acc:.2f}"),
                chart_entry("pp", None, stats.pp),
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
            f"chartUrl:https://{glob.config.domain}/u/{score.player.id}",
            "chartName:Overall Ranking",
            *overall_ranking_chart_entries,
            f"achievements-new:{achievements_str}",
        ]

        ret = "|".join(submission_charts).encode()

    log(
        f"[{score.mode!r}] {score.player} submitted a score! "
        f"({score.status!r}, {score.pp:,.2f}pp / {stats.pp:,}pp)",
        Ansi.LGREEN,
    )

    return ret


@router.get("/web/osu-getreplay.php")
async def getReplay(
    username: str = Query(..., alias="u"),
    pw_md5: str = Query(..., alias="h"),
    mode: int = Query(..., ge=0, le=3),
    score_id: int = Query(..., alias="c"),
):
    if not (
        player := await glob.players.from_login(
            name=unquote(username),
            pw_md5=pw_md5,
        )
    ):
        # player login incorrect
        return

    i64_max = (1 << 63) - 1

    if not 0 < score_id <= i64_max:
        return  # invalid score id

    replay_file = REPLAYS_PATH / f"{score_id}.osr"

    # osu! expects empty resp for no replay
    if replay_file.exists():
        return replay_file.read_bytes()


@router.get("/web/osu-rate.php")
async def osuRate(
    username: str = Query(..., alias="u"),
    pw_md5: str = Query(..., alias="p"),
    map_md5: str = Query(..., alias="c", max_length=32, min_length=32),
    rating: Optional[int] = Query(None, alias="v", ge=1, le=10),
    db_conn: databases.core.Connection = Depends(acquire_db_conn),
):
    if not (
        player := await glob.players.from_login(
            name=unquote(username),
            pw_md5=pw_md5,
        )
    ):
        # player login incorrect
        return b"auth fail"

    if rating is None:
        # check if we have the map in our cache;
        # if not, the map probably doesn't exist.
        if map_md5 not in glob.cache["beatmap"]:
            return b"no exist"

        cached = glob.cache["beatmap"][map_md5]

        # only allow rating on maps with a leaderboard.
        if cached.status < RankedStatus.Ranked:
            return b"not ranked"

        # osu! client is checking whether we can rate the map or not.
        res = await db_conn.fetch_one(
            app.db_models.ratings.select().where(
                sqlalchemy.and_(
                    app.db_models.ratings.c.map_md5 == map_md5,
                    app.db_models.ratings.c.userid == player.id,
                ),
            ),
        )

        # the client hasn't rated the map, so simply
        # tell them that they can submit a rating.
        if not res:
            return b"ok"
    else:
        # the client is submitting a rating for the map.
        await db_conn.execute(
            app.db_models.ratings.insert().values(
                userid=player.id,
                map_md5=map_md5,
                rating=rating,
            ),
        )

    ratings_res = await db_conn.fetch_all(
        app.db_models.ratings.select(app.db_models.ratings.c.ratings).where(
            app.db_models.ratings.c.map_md5 == map_md5,
        ),
    )

    ratings = [r["rating"] for r in ratings_res]

    # send back the average rating
    avg = sum(ratings) / len(ratings)
    return f"alreadyvoted\n{avg}".encode()


@unique
@pymysql_encode(escape_enum)
class LeaderboardType(IntEnum):
    Local = 0
    Top = 1
    Mods = 2
    Friends = 3
    Country = 4


SCORE_LISTING_FMTSTR = (
    "{id}|{name}|{score}|{max_combo}|"
    "{n50}|{n100}|{n300}|{nmiss}|{nkatu}|{ngeki}|"
    "{perfect}|{mods}|{userid}|{rank}|{time}|{has_replay}"
)


@router.get("/web/osu-osz2-getscores.php")
async def getScores(
    get_scores: bool = Query(..., alias="s"),  # NOTE: this is flipped
    leaderboard_version: int = Query(..., alias="vv"),
    leaderboard_type: LeaderboardType = Query(..., alias="v"),
    map_md5: str = Query(..., alias="c", max_length=32, min_length=32),
    map_filename: str = Query(..., alias="f"),  # TODO: regex?
    mode_vn: int = Query(..., alias="m", ge=0, le=3),
    map_set_id: int = Query(..., alias="i", ge=0, le=2_147_483_647),
    mods: Mods = Query(..., ge=0, le=2_147_483_647),
    map_package_hash: str = Query(...),  # TODO: further validation
    aqn_files_found: bool = Query(..., alias="a"),
    username: str = Query(..., alias="us"),
    pw_md5: str = Query(..., alias="ha"),
    db_conn: databases.core.Connection = Depends(acquire_db_conn),
):
    if not (
        player := await glob.players.from_login(
            name=unquote(username),
            pw_md5=pw_md5,
        )
    ):
        # player login incorrect
        return

    # check if this md5 has already been  cached as
    # unsubmitted/needs update to reduce osu!api spam
    if map_md5 in glob.cache["unsubmitted"]:
        return b"-1|false"
    if map_md5 in glob.cache["needs_update"]:
        return b"1|false"

    mode = GameMode.from_params(mode_vn, mods)

    has_set_id = map_set_id > 0

    # attempt to update their stats if their
    # gm/gm-affecting-mods change at all.
    if mode != player.status.mode:
        player.status.mods = mods
        player.status.mode = mode

        if not player.restricted:
            glob.players.enqueue(packets.user_stats(player))

    scores_table = mode.scores_table
    scoring_metric = "pp" if mode >= GameMode.RELAX_OSU else "score"

    bmap = await Beatmap.from_md5(map_md5, set_id=map_set_id)

    if not bmap:
        # map not found, figure out whether it needs an
        # update or isn't submitted using it's filename.

        if has_set_id and map_set_id not in glob.cache["beatmapset"]:
            # set not cached, it doesn't exist
            glob.cache["unsubmitted"].add(map_md5)
            return b"-1|false"

        map_filename = unquote_plus(map_filename)  # TODO: is unquote needed?

        if has_set_id:
            # we can look it up in the specific set from cache
            for bmap in glob.cache["beatmapset"][map_set_id].maps:
                if map_filename == bmap.filename:
                    map_exists = True
                    break
            else:
                map_exists = False
        else:
            # we can't find it on the osu!api by md5,
            # and we don't have the set id, so we must
            # look it up in sql from the filename.
            map_res = await db_conn.fetch_one(
                app.db_models.maps.select().where(
                    app.db_models.maps.c.filename == map_filename,
                ),
            )

            map_exists = map_res is not None

        if map_exists:
            # map can be updated.
            glob.cache["needs_update"].add(map_md5)
            return b"1|false"
        else:
            # map is unsubmitted.
            # add this map to the unsubmitted cache, so
            # that we don't have to make this request again.
            glob.cache["unsubmitted"].add(map_md5)
            return b"-1|false"

    # we've found a beatmap for the request.

    if glob.datadog:
        glob.datadog.increment("gulag.leaderboards_served")

    if bmap.status < RankedStatus.Ranked:
        # only show leaderboards for ranked,
        # approved, qualified, or loved maps.
        return f"{int(bmap.status)}|false".encode()

    alchemy_score_table = getattr(app.db_models, scores_table)
    users_join = join(
        alchemy_score_table,
        app.db_models.users,
        alchemy_score_table.c.userid == app.db_models.users.c.id,
    )
    alchemy_table = join(
        users_join,
        app.db_models.clans,
        users_join.c.clan_id == app.db_models.clans.c.id,
    )

    alchemy_metric = getattr(alchemy_table.c, scoring_metric)

    params = [
        alchemy_table.c.map_md5 == map_md5,
        app.db_models.users.c.priv & 1 or alchemy_table.c.userid == player.id,
        alchemy_table.c.mode == mode_vn,
        alchemy_table.c.status == 2,
    ]

    if leaderboard_type == LeaderboardType.Mods:
        params.append(alchemy_table.c.mods == mods)
    elif leaderboard_type == LeaderboardType.Friends:
        params.append(alchemy_table.c.userid in player.friends | {player.id})
    elif leaderboard_type == LeaderboardType.Country:
        params.append(
            app.db_models.users.c.country == player.geoloc["country"]["acronym"],
        )

    scores = await db_conn.fetch_all(
        select(
            [
                alchemy_table.c.id,
                alchemy_metric,
                alchemy_table.c.max_combo,
                alchemy_table.c.n50,
                alchemy_table.c.n100,
                alchemy_table.c.n300,
                alchemy_table.c.nmiss,
                alchemy_table.c.nkatu,
                alchemy_table.c.ngeki,
                alchemy_table.c.perfect,
                alchemy_table.c.mods,
                alchemy_table.c.play_time.timestamp(),  # type: ignore
                alchemy_table.c.userid,
                app.db_models.users.c.name,
                app.db_models.clans.c.tag,
            ],
        )
        .select_from(alchemy_table)
        .where(sqlalchemy.and_(*params))
        .order_by(alchemy_metric.desc())
        .limit(50),
    )

    num_scores = len(scores)

    l: list[str] = []

    # ranked status, serv has osz2, bid, bsid, len(scores)
    l.append(f"{int(bmap.status)}|false|{bmap.id}|{bmap.set_id}|{num_scores}")

    # fetch beatmap rating from sql
    rating = await db_conn.fetch_val(
        app.db_models.ratings.select(func.avg(app.db_models.ratings.c.rating)).where(
            app.db_models.ratings.c.map_md5 == map_md5,
        ),
        column=0,
    )

    if rating is not None:
        rating = f"{rating:.1f}"
    else:
        rating = "10.0"

    # TODO: we could have server-specific offsets for
    # maps that mods could set for incorrectly timed maps.
    l.append(f"0\n{bmap.full}\n{rating}")  # offset, name, rating

    if not scores:
        # simply return an empty set.
        return ("\n".join(l) + "\n\n").encode()

    # fetch player's personal best score
    p_best = await db_conn.fetch_one(
        select(
            [
                alchemy_score_table.c.id,
                alchemy_metric,
                alchemy_score_table.c.max_combo,
                alchemy_score_table.c.n50,
                alchemy_score_table.c.n100,
                alchemy_score_table.c.n300,
                alchemy_score_table.c.nmiss,
                alchemy_score_table.c.nkatu,
                alchemy_score_table.c.ngeki,
                alchemy_score_table.c.perfect,
                alchemy_score_table.c.mods,
                alchemy_score_table.c.play_time.timestamp(),  # type: ignore
            ],
        )
        .where(
            sqlalchemy.and_(
                alchemy_score_table.c.map_md5 == map_md5,
                alchemy_score_table.c.userid == player.id,
                alchemy_score_table.c.mode == mode_vn,
                alchemy_score_table.c.status == 2,
            ),
        )
        .order_by(alchemy_metric.desc())
        .limit(1),
    )

    if p_best:
        # calculate the rank of the score.
        p_best_rank = await db_conn.fetch_val(
            select([func.count(alchemy_metric) + 1])
            .where(
                sqlalchemy.and_(
                    alchemy_metric > p_best[scoring_metric],
                    alchemy_table.c.map_md5 == map_md5,
                    alchemy_table.c.mode == mode_vn,
                    alchemy_table.c.status == 2,
                    app.db_models.users.c.priv & 1,
                ),
            )
            .select_from(users_join),
            column=0,
        )

        l.append(
            SCORE_LISTING_FMTSTR.format(
                **p_best,
                name=player.full_name,
                userid=player.id,
                score=int(p_best[alchemy_metric]),
                has_replay="1",
                rank=p_best_rank,
            ),
        )
    else:
        l.append("")

    l.extend(
        [
            SCORE_LISTING_FMTSTR.format(
                **s, score=int(s[scoring_metric]), has_replay="1", rank=idx + 1
            )
            for idx, s in enumerate(scores)
        ],
    )

    return "\n".join(l).encode()


@router.post("/web/osu-comment.php")
async def osuComment(
    username: str = Query(..., alias="u"),
    pw_md5: str = Query(..., alias="p"),
    beatmap_id: int = Query(..., alias="b"),
    beatmap_set_id: int = Query(..., alias="s"),
    score_id: int = Query(..., alias="r", ge=0, le=2_147_483_647),
    mode_vn: int = Query(..., alias="m", ge=0, le=3),
    action: Literal["get", "post"] = Query(..., alias="a"),
    # only sent for post
    target: Optional[Literal["song", "map", "replay"]] = Query(None),
    colour: Optional[str] = Query(None, alias="f", min_length=6, max_length=6),
    start_time: Optional[int] = Query(None, alias="starttime"),
    comment: Optional[str] = Query(None, min_length=1, max_length=80),
    db_conn: databases.core.Connection = Depends(acquire_db_conn),
):
    if not (
        player := await glob.players.from_login(
            name=unquote(username),
            pw_md5=pw_md5,
        )
    ):
        # player login incorrect
        return

    if action == "get":
        # client is requesting all comments
        comment_user_join = join(
            app.db_models.comments,
            app.db_models.users,
            app.db_models.users.c.id == app.db_models.comments.c.userid,
        )
        comments = await db_conn.fetchall(
            select(
                [
                    app.db_models.comments.c.time,
                    app.db_models.comments.c.target_type,
                    app.db_models.comments.c.colour,
                    app.db_models.comments.c.comment,
                    app.db_models.users.c.priv,
                ],
            )
            .select_from(comment_user_join)
            .where(
                sqlalchemy.or_(
                    app.db_models.comments.c.target_type == "replay"
                    and app.db_models.comments.c.target_id == score_id,
                    app.db_models.comments.c.target_type == "map"
                    and app.db_models.comments.c.target_id == beatmap_id,
                    app.db_models.comments.c.target_type == "song"
                    and app.db_models.comments.c.target_id == beatmap_set_id,
                ),
            ),
        )

        ret: list[str] = []

        for cmt in comments:
            # TODO: maybe support player/creator colours?
            # pretty expensive for very low gain, but completion :D
            if cmt["priv"] & Privileges.NOMINATOR:
                fmt = "bat"
            elif cmt["priv"] & Privileges.DONATOR:
                fmt = "supporter"
            else:
                fmt = ""

            if cmt["colour"]:
                fmt += f"|{cmt['colour']}"

            ret.append(
                "{time}\t{target_type}\t" "{fmt}\t{comment}".format(fmt=fmt, **cmt),
            )

        await player.update_latest_activity()
        return "\n".join(ret).encode()

    else:  # action == "post":
        # client is submitting a new comment
        # TODO: maybe validate all params are sent?

        # get the corresponding id from the request
        if target == "song":
            target_id = beatmap_set_id
        elif target == "map":
            target_id = beatmap_id
        else:  # target == "replay"
            target_id = score_id

        if colour and not player.priv & Privileges.DONATOR:
            # only supporters can use colours.
            # TODO: should we be restricting them?
            colour = None

        # insert into sql
        await db_conn.execute(
            app.db_models.comments.insert().values(
                {
                    "target_id": target_id,
                    "target": target,
                    "userid": player.id,
                    "start_time": start_time,
                    "comment": comment,
                    "colour": colour,
                },
            ),
        )

        await player.update_latest_activity()
        return  # empty resp is fine


@router.get("/web/osu-markasread.php")
async def osuMarkAsRead(
    channel: str,  # TODO: further validation?
    username: str = Query(..., alias="u"),
    pw_md5: str = Query(..., alias="h"),
    db_conn: databases.core.Connection = Depends(acquire_db_conn),
):
    if not (
        player := await glob.players.from_login(
            name=unquote(username),
            pw_md5=pw_md5,
        )
    ):
        # player login incorrect
        return

    if not (t_name := unquote(channel)):  # TODO: unquote needed?
        return  # no channel specified

    if t := await glob.players.from_cache_or_sql(name=t_name):
        # mark any unread mail from this user as read.
        await db_conn.execute(
            app.db_models.mail.update()
            .values(read=1)
            .where(
                sqlalchemy.and_(
                    app.db_models.mail.c.to_id == player.id,
                    app.db_models.mail.c.from_id == t.id,
                    app.db_models.mail.c.read == 0,
                ),
            ),
        )


@router.get("/web/osu-getseasonal.php")
async def osuSeasonal():
    return orjson.dumps(glob.config.seasonal_bgs)


@router.get("/web/bancho_connect.php")
async def banchoConnect(
    osu_ver: str = Query(..., alias="v"),
    username: str = Query(..., alias="u"),
    pw_md5: str = Query(..., alias="h"),
    #
    active_endpoint: Optional[str] = Query(None, alias="fail"),
    net_framework_vers: Optional[str] = Query(None, alias="fx"),  # delimited by |
    client_hash: Optional[str] = Query(None, alias="ch"),
    retrying: Optional[bool] = Query(None, alias="retry"),  # '0' or '1'
):
    return b""  # TODO


_checkupdates_cache = {  # default timeout is 1h, set on request.
    "cuttingedge": {"check": None, "path": None, "timeout": 0},
    "stable40": {"check": None, "path": None, "timeout": 0},
    "beta40": {"check": None, "path": None, "timeout": 0},
    "stable": {"check": None, "path": None, "timeout": 0},
}

# NOTE: this will only be triggered when using a server switcher.
@router.get("/web/check-updates.php")
async def checkUpdates(
    request: Request,
    action: Literal["check", "path", "error"],
    stream: Literal["cuttingedge", "stable40", "beta40", "stable"],
):
    if action == "error":
        # client is just reporting an error updating
        return

    cache = _checkupdates_cache[stream]
    current_time = int(time.time())

    if cache[action] and cache["timeout"] > current_time:
        return cache[action]

    url = "https://old.ppy.sh/web/check-updates.php"
    async with app.services.http_session.get(url, params=request.query_params) as resp:
        if not resp or resp.status != 200:
            return (503, b"")  # failed to get data from osu

        result = await resp.read()

    # update the cached result.
    cache[action] = result
    cache["timeout"] = glob.config.updates_cache_timeout + current_time

    return result


""" Misc handlers """

if glob.config.redirect_osu_urls:
    """Redirect commonly visited osu! pages to osu!'s website."""

    @router.get("/beatmapsets/{map_set_id}")
    async def mapset_web_handler(
        request: Request,
        map_set_id: int = Path(..., ge=0, le=2_147_483_647),
    ):
        return RedirectResponse(
            url=f"https://osu.ppy.sh/{request['path']}",
            status_code=status.HTTP_301_MOVED_PERMANENTLY,
        )

    @router.get("/beatmaps/{map_id}")
    async def map_web_handler(
        request: Request,
        map_id: int = Path(..., ge=0, le=2_147_483_647),
    ):
        return RedirectResponse(
            url=f"https://osu.ppy.sh/{request['path']}",
            status_code=status.HTTP_301_MOVED_PERMANENTLY,
        )

    @router.get("/community/forums/topics/{topic_id}")
    async def forum_web_handler(
        request: Request,
        topic_id: int = Path(..., ge=0, le=2_147_483_647),
    ):
        return RedirectResponse(
            url=f"https://osu.ppy.sh/{request['path']}",
            status_code=status.HTTP_301_MOVED_PERMANENTLY,
        )


@router.get("/ss/{screenshot_id}.{extension}")
async def get_screenshot(
    screenshot_id: str = Path(..., regex=r"[a-zA-Z0-9-_]{8}"),
    extension: Literal["jpg", "jpeg", "png"] = Path(...),
):
    """Serve a screenshot from the server, by filename."""
    screenshot_path = SCREENSHOTS_PATH / f"{screenshot_id}.{extension}"

    if not screenshot_path.exists():
        return ORJSONResponse(
            {"status": "Screenshot not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return FileResponse(
        screenshot_path,
        media_type=app.misc.utils.get_media_type(extension),
    )


# TODO: this surely doesn't work
@router.get("/d/{map_set_id}{no_video}")
async def get_osz(
    map_set_id: int = Path(..., ge=0, le=2_147_483_647),
    no_video: Optional[Literal["n"]] = Path(...),
):
    """Handle a map download request (osu.ppy.sh/d/*)."""
    download_video = not no_video

    if USING_CHIMU:
        query_str = f"download/{map_set_id}?n={int(not download_video)}"
    else:
        query_str = f"d/{map_set_id}"

    return RedirectResponse(
        url=f"{app.settings.MIRROR_URL}/{query_str}",
        status_code=status.HTTP_301_MOVED_PERMANENTLY,
    )


@router.get("/web/maps/{map_filename}")
async def get_updated_beatmap(
    request: Request,
    map_filename: str,
    host: str = Header(...),
    db_conn: databases.core.Connection = Depends(acquire_db_conn),
):
    """Send the latest .osu file the server has for a given map."""
    if host != "osu.ppy.sh":
        # using -devserver, just redirect them to osu
        return RedirectResponse(
            f"https://osu.ppy.sh{request['path']}",
            status_code=status.HTTP_301_MOVED_PERMANENTLY,
        )

    # server switcher, use old method
    map_filename = unquote(map_filename)

    row = await db_conn.fetch_one(
        select([app.db_models.maps.c.id, app.db_models.maps.c.md5]).where(
            app.db_models.maps.c.filename == map_filename,
        ),
    )

    if not row:
        return (404, b"")  # map not found in sql

    osu_file_path = BEATMAPS_PATH / f'{row["id"]}.osu'

    if (
        osu_file_path.exists()
        and row["md5"] == hashlib.md5(osu_file_path.read_bytes()).hexdigest()
    ):
        # up to date map found on disk.
        content = osu_file_path.read_bytes()
    else:
        # map not found, or out of date; get from osu!
        url = f"https://old.ppy.sh/osu/{row['id']}"

        async with app.services.http_session.get(url) as resp:
            if not resp or resp.status != 200:
                log(f"Could not find map {osu_file_path}!", Ansi.LRED)
                return (404, b"")  # couldn't find on osu!'s server

            content = await resp.read()

        # save it to disk for future
        osu_file_path.write_bytes(content)

    return content


@router.route("/p/doyoureallywanttoaskpeppy")
async def peppyDMHandler():
    return (
        b"This user's ID is usually peppy's (when on bancho), "
        b"and is blocked from being messaged by the osu! client."
    )


""" ingame registration """


@router.route("/users", methods=["POST"])
@ratelimit(period=300, max_count=15)  # 15 registrations / 5mins
async def register_account(
    db_conn: databases.core.Connection = Depends(acquire_db_conn),
    username: str = Form(..., alias="user[username]"),
    email: str = Form(..., alias="user[user_email]"),
    pw_plaintext: str = Form(..., alias="user[password]"),
    check: int = Form(...),
    # this sucks
    cloudflare_country: Optional[str] = Header(None, alias="CF-IPCountry"),
    cloudflare_ip: Optional[str] = Header(None, alias="CF-Connecting-IP"),
    forwarded_ip: Optional[str] = Header(None, alias="X-Forwarded-For"),
    real_ip: Optional[str] = Header(None, alias="X-Real-IP"),
):
    safe_name = username.lower().replace(" ", "_")

    if not all((username, email, pw_plaintext, check)):
        return (400, b"Missing required params")

    # ensure all args passed
    # are safe for registration.
    errors: Mapping[str, list[str]] = defaultdict(list)

    # Usernames must:
    # - be within 2-15 characters in length
    # - not contain both ' ' and '_', one is fine
    # - not be in the config's `disallowed_names` list
    # - not already be taken by another player
    if not regexes.USERNAME.match(username):
        errors["username"].append("Must be 2-15 characters in length.")

    if "_" in username and " " in username:
        errors["username"].append('May contain "_" and " ", but not both.')

    if username in glob.config.disallowed_names:
        errors["username"].append("Disallowed username; pick another.")

    if "username" not in errors:
        res = await db_conn.fetch_one(
            app.db_models.users.select().where(
                app.db_models.users.c.safe_name == safe_name,
            ),
        )

        if res:
            errors["username"].append("Username already taken by another player.")

    # Emails must:
    # - match the regex `^[^@\s]{1,200}@[^@\s\.]{1,30}\.[^@\.\s]{1,24}$`
    # - not already be taken by another player
    if not regexes.EMAIL.match(email):
        errors["user_email"].append("Invalid email syntax.")
    else:
        res = await db_conn.fetch_one(
            app.db_models.users.select().where(app.db_models.users.c.email == email),
        )

        if res:
            errors["user_email"].append("Email already taken by another player.")

    # Passwords must:
    # - be within 8-32 characters in length
    # - have more than 3 unique characters
    # - not be in the config's `disallowed_passwords` list
    if not 8 <= len(pw_plaintext) <= 32:
        errors["password"].append("Must be 8-32 characters in length.")

    if len(set(pw_plaintext)) <= 3:
        errors["password"].append("Must have more than 3 unique characters.")

    if pw_plaintext.lower() in glob.config.disallowed_passwords:
        errors["password"].append("That password was deemed too simple.")

    if errors:
        # we have errors to send back, send them back delimited by newlines.
        errors = {k: ["\n".join(v)] for k, v in errors.items()}
        errors_full = {"form_error": {"user": errors}}
        return (400, orjson.dumps(errors_full))

    if check == 0:
        # the client isn't just checking values,
        # they want to register the account now.
        # make the md5 & bcrypt the md5 for sql.
        async with glob.players._lock:
            pw_md5 = hashlib.md5(pw_plaintext.encode()).hexdigest().encode()
            pw_bcrypt = bcrypt.hashpw(pw_md5, bcrypt.gensalt())
            glob.cache["bcrypt"][pw_bcrypt] = pw_md5  # cache result for login

            if cloudflare_country:
                # best case, dev has enabled ip geolocation in the
                # network tab of cloudflare, so it sends the iso code.
                country_acronym = cloudflare_country
            else:
                # backup method, get the user's ip and
                # do a db lookup to get their country.
                if cloudflare_ip:
                    ip_str = cloudflare_ip
                else:
                    # if the request has been forwarded, get the origin
                    forwards = forwarded_ip.split(",")  # type: ignore
                    if len(forwards) != 1:
                        ip_str = forwards[0]
                    else:
                        ip_str = real_ip

                if ip_str in glob.cache["ip"]:
                    ip = glob.cache["ip"][ip_str]
                else:
                    ip = ipaddress.ip_address(ip_str)
                    glob.cache["ip"][ip_str] = ip

                if not ip.is_private:
                    if glob.geoloc_db is not None:
                        # decent case, dev has downloaded a geoloc db from
                        # maxmind, so we can do a local db lookup. (~1-5ms)
                        # https://www.maxmind.com/en/home
                        geoloc = app.misc.utils.fetch_geoloc_db(ip)
                    else:
                        # worst case, we must do an external db lookup
                        # using a public api. (depends, `ping ip-api.com`)
                        geoloc = await app.misc.utils.fetch_geoloc_web(ip)

                    country_acronym = geoloc["country"]["acronym"]
                else:
                    # localhost, unknown country
                    country_acronym = "xx"

            # add to `users` table.
            user_id = await db_conn.execute(
                app.db_models.users.insert()
                .values(
                    {
                        "name": username,
                        "safe_name": safe_name,
                        "email": email,
                        "pw_bcrypt": pw_bcrypt,
                        "country": country_acronym,
                        "creation_time": func.unix_timestamp(),
                        "latest_activity": func.unix_timestamp(),
                    },
                )
                .returning(app.db_models.users.c.id),
            )

            # add to `stats` table.
            for mode in range(8):
                await db_conn.execute(
                    app.db_models.stats.insert().values({"id": user_id, "mode": mode}),
                )

        if glob.datadog:
            glob.datadog.increment("gulag.registrations")

        log(f"<{username} ({user_id})> has registered!", Ansi.LGREEN)

    return b"ok"  # success


@router.route("/difficulty-rating", methods=["POST"])
async def difficultyRatingHandler(request: Request) -> Response:
    return RedirectResponse(
        f"https://osu.ppy.sh{request['path']}",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )
