""" osu: handle connections from web, api, and beyond? """
# TODO: remove beyond part from this file
import copy
import hashlib
import ipaddress
import random
import re
import secrets
import struct
import time
from base64 import b64decode
from collections import defaultdict
from enum import IntEnum
from enum import unique
from functools import wraps
from pathlib import Path
from typing import Any
from typing import AsyncIterator
from typing import Awaitable
from typing import Callable
from typing import Literal
from typing import Mapping
from typing import Optional
from typing import TYPE_CHECKING
from typing import Union
from urllib.parse import unquote
from urllib.parse import unquote_plus

import aiomysql
import bcrypt
import databases.core
import misc.utils
import orjson
from cmyui.logging import Ansi
from cmyui.logging import log
from cmyui.logging import printc
from cmyui.web import Connection
from cmyui.web import Domain
from cmyui.web import ratelimit
from constants import regexes
from constants.clientflags import ClientFlags
from constants.gamemodes import GameMode
from constants.mods import Mods
from fastapi import APIRouter
from fastapi import Depends
from fastapi import status
from fastapi.datastructures import UploadFile
from fastapi.param_functions import File
from fastapi.param_functions import Form
from fastapi.param_functions import Query
from fastapi.requests import Request
from fastapi.responses import ORJSONResponse
from fastapi.responses import Response
from fastapi.responses import StreamingResponse
from misc.utils import escape_enum
from misc.utils import pymysql_encode
from objects import glob
from objects.beatmap import Beatmap
from objects.beatmap import ensure_local_osu_file
from objects.beatmap import RankedStatus
from objects.player import Privileges
from objects.score import Grade
from objects.score import Score
from objects.score import SubmissionStatus
from py3rijndael import Pkcs7Padding
from py3rijndael import RijndaelCbc
from pydantic import BaseModel

import packets
from app import services

if TYPE_CHECKING:
    from objects.player import Player

AVATARS_PATH = Path.cwd() / ".data/avatars"
BEATMAPS_PATH = Path.cwd() / ".data/osu"
REPLAYS_PATH = Path.cwd() / ".data/osr"
SCREENSHOTS_PATH = Path.cwd() / ".data/ss"

router = APIRouter()


async def acquire_db_conn(f: Callable) -> AsyncIterator[databases.core.Connection]:
    """Decorator to acquire a database connection for a handler."""
    async with services.database.connection() as conn:
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
            await misc.utils.log_strange_occurrence("osu-error auth failed")
            player = None
    else:
        player = None

    err_desc = f"{feedback} ({exception})"
    log(f'{player or "Offline user"} sent osu-error: {err_desc}', Ansi.LCYAN)

    # NOTE: this stacktrace can be a LOT of data
    if glob.config.debug and len(stacktrace) < 2000:
        printc(stacktrace[:-2], Ansi.LMAGENTA)

    # TODO: save error in db?
    pass


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
        await misc.utils.log_strange_occurrence(
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
        row = await db_conn.execute(
            "SELECT id, set_id, status, md5 FROM maps WHERE filename = :filename",
            {"filename": map_filename},
        )

        # convert from gulag -> osu!api status
        row["status"] = gulag_to_osuapi_status(row["status"])

        # try to get the user's grades on the map osu!
        # only allows us to send back one per gamemode,
        # so we'll just send back relax for the time being..
        # XXX: perhaps user-customizable in the future?
        grades = ["N", "N", "N", "N"]

        async for score in db_conn.iterate(
            "SELECT grade, mode FROM scores_rx "
            "WHERE map_md5 = :map_md5 AND userid = :userid "
            "AND status = 2",
            {"map_md5": row["md5"], "userid": player.id},
        ):
            grades[score["mode"]] = score["grade"]

        ret.append(
            "{i}|{id}|{set_id}|{md5}|{status}|{grades}".format(
                **row, i=idx, grades="|".join(grades)
            ),
        )

    if form_data.Ids:  # still have yet to see this used
        await misc.utils.log_strange_occurrence(
            f"{player} requested map(s) info by id ({form_data.Ids})",
        )

    return "\n".join(ret).encode()


@router.get("/web/osu-getfavourites.php")
async def osuGetFavourites(
    username: str = Query(..., alias="u"),
    pw_md5: str = Query(..., alias="h"),
):
    if not (
        player := await glob.players.from_login(
            name=unquote(username),
            pw_md5=pw_md5,
        )
    ):
        # player login incorrect
        return

    favourites = await services.database.fetch_all(
        "SELECT setid FROM favourites WHERE userid = :userid",
        {"userid": player.id},
    )

    return "\n".join([row["setid"] for row in favourites]).encode()


@router.get("/web/osu-addfavourite.php")
async def osuAddFavourite(
    username: str = Query(..., alias="u"),
    pw_md5: str = Query(..., alias="h"),
    map_set_id: int = Query(..., alias="a"),
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
    if await services.database.fetch_one(
        "SELECT 1 FROM favourites WHERE userid = :userid AND setid = :setid",
        {"1": player.id, "setid": map_set_id},
    ):
        return b"You've already favourited this beatmap!"

    # add favourite
    await services.database.execute(
        "INSERT INTO favourites VALUES (:id, :setid)",
        {"id": player.id, "setid": map_set_id},
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

    if not glob.has_internet:
        return b"-1\nosu!direct requires an internet connection."

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

    async with glob.http_session.get(search_url, params=params) as resp:
        if not resp:
            stacktrace = misc.utils.get_appropriate_stacktrace()
            await misc.utils.log_strange_occurrence(stacktrace)

        if USING_CHIMU:  # error handling varies
            if resp.status == 404:
                return b"0"  # no maps found
            elif resp.status >= 500:  # chimu server error (happens a lot :/)
                return b"-1\nFailed to retrieve data from the beatmap mirror."
            elif resp.status != 200:
                stacktrace = misc.utils.get_appropriate_stacktrace()
                await misc.utils.log_strange_occurrence(stacktrace)
                return b"-1\nFailed to retrieve data from the beatmap mirror."
        else:  # cheesegull
            if resp.status != 200:
                return b"-1\nFailed to retrieve data from the beatmap mirror."

        result = await resp.json()

        if USING_CHIMU:
            if result["code"] != 0:
                stacktrace = misc.utils.get_appropriate_stacktrace()
                await misc.utils.log_strange_occurrence(stacktrace)
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
        k, v = ("set_id", map_set_id)
    elif map_id is not None:
        k, v = ("id", map_id)
    else:
        return  # invalid args

    # Get all set data.
    bmapset = await services.database.fetch_one(
        "SELECT DISTINCT set_id, artist, "
        "title, status, creator, last_update "
        f"FROM maps WHERE {k} = :v",
        {"v": v},
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
    score.player.update_latest_activity()

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
    duplicate_score = await db_conn.fetch_one(
        f"SELECT 1 FROM {scores_table} WHERE online_checksum = :online_checksum",
        {"online_checksum": score.online_checksum},
    )

    if duplicate_score:
        log(f"{score.player} submitted a duplicate score.", Ansi.LYELLOW)
        return b"error: no"

    time_elapsed = score_time if score.passed else fail_time

    score.time_elapsed = int(time_elapsed)

    if fl_cheat_screenshot:
        stacktrace = misc.utils.get_appropriate_stacktrace()
        await misc.utils.log_strange_occurrence(stacktrace)

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
                prev_n1 = await db_conn.fetch_one(
                    "SELECT u.id, name FROM users u "
                    f"INNER JOIN {scores_table} s ON u.id = s.userid "
                    "WHERE s.map_md5 = :map_md5 AND s.mode = :mode_vn "
                    "AND s.status = 2 AND u.priv & 1 "
                    f"ORDER BY s.{scoring_metric} DESC LIMIT 1",
                    {"map_md5": score.bmap.md5, "mode_vn": mode_vn},
                )

                if prev_n1:
                    if score.player.id != prev_n1["id"]:
                        ann.append(
                            f"(Previous #1: [https://{glob.config.domain}/u/"
                            "{pid} {pname}])".format(**prev_n1),
                        )

                announce_chan.send(" ".join(ann), sender=score.player, to_self=True)

        # this score is our best score.
        # update any preexisting personal best
        # records with SubmissionStatus.SUBMITTED.
        await db_conn.execute(
            f"UPDATE {scores_table} SET status = 1 "
            "WHERE status = 2 AND map_md5 = :map_md5 "
            "AND userid = :userid AND mode = :mode_vn",
            {"map_md5": score.bmap.md5, "userid": score.player.id, "mode_vn": mode_vn},
        )

    score.id = await db_conn.execute(
        f"INSERT INTO {scores_table} "
        "VALUES (NULL, "
        ":map_md5 , :score, :pp, :acc, "
        ":max_combo, :mods, :n300, :n100, "
        ":n50, :nmiss, :ngeki, :nkatu, "
        ":grade, :status, :mode_vn, :play_time, "
        ":time_elapsed, :client_flags, :userid, :perfect, "
        ":online_checksum)",
        {
            "map_md5": score.bmap.md5,
            "score": score.score,
            "pp": score.pp,
            "acc": score.acc,
            "max_combo": score.max_combo,
            "mods": score.mods,
            "n300": score.n300,
            "n100": score.n100,
            "n50": score.n50,
            "nmiss": score.nmiss,
            "ngeki": score.ngeki,
            "nkatu": score.nkatu,
            "grade": score.grade.name,
            "status": score.status,
            "mode_vn": mode_vn,
            "play_time": score.play_time,
            "time_elapsed": score.time_elapsed,
            "client_flags": score.client_flags,
            "userid": score.player.id,
            "perfect": score.perfect,
            "online_checksum": score.online_checksum,
        },
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

    stats_query_l = [
        "UPDATE stats SET plays = :plays, playtime = :playtime, tscore = :tscore",
    ]

    stats_query_args: dict[str, object] = {
        "plays": stats.plays,
        "playtime": stats.playtime,
        "tscore": stats.tscore,
    }

    if score.passed and score.bmap.has_leaderboard:
        # player passed & map is ranked, approved, or loved.

        if score.max_combo > stats.max_combo:
            stats.max_combo = score.max_combo
            stats_query_l.append("max_combo = :max_combo")
            stats_query_args["max_combo"] = stats.max_combo

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
                        stats_query_l.append(f"{grade_col} = {grade_col} + 1")

                    if score.prev_best.grade >= Grade.A:
                        stats.grades[score.prev_best.grade] -= 1
                        grade_col = format(score.prev_best.grade, "stats_column")
                        stats_query_l.append(f"{grade_col} = {grade_col} - 1")
            else:
                # this is our first submitted score on the map
                if score.grade >= Grade.A:
                    stats.grades[score.grade] += 1
                    grade_col = format(score.grade, "stats_column")
                    stats_query_l.append(f"{grade_col} = {grade_col} + 1")

            stats.rscore += additional_rscore
            stats_query_l.append("rscore = :rscore")
            stats_query_args["rscore"] = stats.rscore

            # fetch scores sorted by pp for total acc/pp calc
            # NOTE: we select all plays (and not just top100)
            # because bonus pp counts the total amount of ranked
            # scores. i'm aware this scales horribly and it'll
            # likely be split into two queries in the future.
            rows = await db_conn.fetch_all(
                f"SELECT s.pp, s.acc FROM {scores_table} s "
                "INNER JOIN maps m ON s.map_md5 = m.md5 "
                "WHERE s.userid = :userid AND s.mode = :mode_vn "
                "AND s.status = 2 AND m.status IN (2, 3) "  # ranked, approved
                "ORDER BY s.pp DESC",
                {"userid": score.player.id, "mode_vn": mode_vn},
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
            stats_query_l.append("acc = :acc")
            stats_query_args["acc"] = stats.acc

            # calculate new total weighted pp
            weighted_pp = sum(
                [row["pp"] * 0.95 ** i for i, row in enumerate(top_100_pp)],
            )
            bonus_pp = 416.6667 * (1 - 0.95 ** total_scores)
            stats.pp = round(weighted_pp + bonus_pp)

            # add pp to query
            stats_query_l.append("pp = :pp")
            stats_query_args["pp"] = stats.pp

            # update rank
            stats.rank = await score.player.update_rank(score.mode)

    # create a single querystring from the list of updates
    stats_query = ",".join(stats_query_l)

    stats_query += " WHERE id = :userid AND mode = :mode"
    stats_query_args["userid"] = score.player.id
    stats_query_args["mode"] = score.mode.value

    # send any stat changes to sql, and other players
    await db_conn.execute(stats_query, stats_query_args)
    glob.players.enqueue(packets.user_stats(score.player))

    if not score.player.restricted:
        # update beatmap with new stats
        score.bmap.plays += 1
        if score.passed:
            score.bmap.passes += 1

        await db_conn.execute(
            "UPDATE maps SET plays = :plays, passes = :passes WHERE md5 = :map_md5",
            {
                "plays": score.bmap.plays,
                "passes": score.bmap.passes,
                "map_md5": score.bmap.md5,
            },
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
        row = await db_conn.fetch_one(
            "SELECT 1 FROM ratings WHERE map_md5 = :map_md5 AND userid = :userid",
            {"map_md5": map_md5, "userid": player.id},
        )

        # the client hasn't rated the map, so simply
        # tell them that they can submit a rating.
        if not row:
            return b"ok"
    else:
        # the client is submitting a rating for the map.
        await db_conn.execute(
            "INSERT INTO ratings VALUES (:userid, :map_md5, :rating)",
            {"userid": player.id, "map_md5": map_md5, "rating": rating},
        )

    ratings = [
        row[0]
        async for row in db_conn.iterate(
            "SELECT rating FROM ratings WHERE map_md5 = :map_md5",
            {"map_md5": map_md5},
        )
    ]

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
            map_exists = (
                await db_conn.fetch_one(
                    "SELECT 1 FROM maps WHERE filename = :filename",
                    {"filename": map_filename},
                )
                is not None
            )

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

    # statuses: 0: failed, 1: passed but not top, 2: passed top
    query = [
        f"SELECT s.id, s.{scoring_metric} AS _score, "
        "s.max_combo, s.n50, s.n100, s.n300, "
        "s.nmiss, s.nkatu, s.ngeki, s.perfect, s.mods, "
        "UNIX_TIMESTAMP(s.play_time) time, u.id userid, "
        "COALESCE(CONCAT('[', c.tag, '] ', u.name), u.name) AS name "
        f"FROM {scores_table} s "
        "INNER JOIN users u ON u.id = s.userid "
        "LEFT JOIN clans c ON c.id = u.clan_id "
        "WHERE s.map_md5 = :map_md5 AND s.status = 2 "
        "AND (u.priv & 1 OR u.id = :userid) AND mode = :mode_vn",
    ]

    params = {
        "map_md5": map_md5,
        "userid": player.id,
        "mode_vn": mode_vn,
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

    query.append("ORDER BY _score DESC LIMIT 50")

    scores = await db_conn.fetch_all(" ".join(query), params)
    num_scores = len(scores)

    l: list[str] = []

    # ranked status, serv has osz2, bid, bsid, len(scores)
    l.append(f"{int(bmap.status)}|false|{bmap.id}|{bmap.set_id}|{num_scores}")

    # fetch beatmap rating from sql
    rating = await db_conn.fetch_val(
        "SELECT AVG(rating) rating FROM ratings WHERE map_md5 = :map_md5",
        {"map_md5": bmap.md5},
        column=2,  # rating # TODO test if str/int
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
        f"SELECT id, {scoring_metric} AS _score, "
        "max_combo, n50, n100, n300, "
        "nmiss, nkatu, ngeki, perfect, mods, "
        "UNIX_TIMESTAMP(play_time) time "
        f"FROM {scores_table} "
        "WHERE map_md5 = :map_md5 AND mode = :mode_vn "
        "AND userid = :userid AND status = 2 "
        "ORDER BY _score DESC LIMIT 1",
        {
            "map_md5": map_md5,
            "mode_vn": mode_vn,
            "userid": player.id,
        },
    )

    if p_best:
        # calculate the rank of the score.
        p_best_rank = 1 + (
            await db_conn.fetch_val(
                f"SELECT COUNT(*) AS count FROM {scores_table} s "
                "INNER JOIN users u ON u.id = s.userid "
                "WHERE s.map_md5 = :map_md5 AND s.mode = :mode_vn "
                "AND s.status = 2 AND u.priv & 1 "
                f"AND s.{scoring_metric} > :score",
                {
                    "map_md5": map_md5,
                    "mode_vn": mode_vn,
                    "score": p_best["_score"],
                },
                column=0,
            )
        )

        l.append(
            SCORE_LISTING_FMTSTR.format(
                **p_best,
                name=player.full_name,
                userid=player.id,
                score=int(p_best["_score"]),
                has_replay="1",
                rank=p_best_rank,
            ),
        )
    else:
        l.append("")

    l.extend(
        [
            SCORE_LISTING_FMTSTR.format(
                **s, score=int(s["_score"]), has_replay="1", rank=idx + 1
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
        comments = await services.database.fetch_all(
            "SELECT c.time, c.target_type, c.colour, "
            "c.comment, u.priv FROM comments c "
            "INNER JOIN users u ON u.id = c.userid "
            "WHERE (c.target_type = 'replay' AND c.target_id = :score_id) "
            "OR (c.target_type = 'song' AND c.target_id = :map_set_id) "
            "OR (c.target_type = 'map' AND c.target_id = :map_id) ",
            {
                "score_id": score_id,
                "map_set_id": beatmap_set_id,
                "map_id": beatmap_id,
            },
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
                fmt += f'|{cmt["colour"]}'

            ret.append(
                "{time}\t{target_type}\t" "{fmt}\t{comment}".format(fmt=fmt, **cmt),
            )

        player.update_latest_activity()
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
        await services.database.execute(
            "INSERT INTO comments "
            "(target_id, target_type, userid, time, comment, colour) "
            "VALUES (:target_id, :target, :userid, :start_time, :comment, :colour)",
            {
                "target_id": target_id,
                "target": target,
                "userid": player.id,
                "start_time": start_time,
                "comment": comment,
                "colour": colour,
            },
        )

        player.update_latest_activity()
        return  # empty resp is fine


@router.get("/web/osu-markasread.php")
async def osuMarkAsRead(
    channel: str,  # TODO: further validation?
    username: str = Query(..., alias="u"),
    pw_md5: str = Query(..., alias="h"),
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
        await services.database.execute(
            "UPDATE `mail` SET `read` = 1 "
            "WHERE `to_id` = :to_id AND `from_id` = :from_id "
            "AND `read` = 0",
            {"to_id": player.id, "to_id": t.id},
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
    if not glob.has_internet:
        return (503, b"")  # requires internet connection

    if action == "error":
        # client is just reporting an error updating
        return

    cache = _checkupdates_cache[stream]
    current_time = int(time.time())

    if cache[action] and cache["timeout"] > current_time:
        return cache[action]

    url = "https://old.ppy.sh/web/check-updates.php"
    async with glob.http_session.get(url, params=request.query_params) as resp:
        if not resp or resp.status != 200:
            return (503, b"")  # failed to get data from osu

        result = await resp.read()

    # update the cached result.
    cache[action] = result
    cache["timeout"] = glob.config.updates_cache_timeout + current_time

    return result


""" /api/ Handlers """
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
    total_users = await services.database.fetch_val(
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
        user_info = await services.database.fetch_one(
            "SELECT id, name, safe_name, "
            "priv, country, silence_end "
            "FROM users WHERE safe_name = :username",
            {"username": username.lower()},
        )
    else:  # if user_id
        user_info = await services.database.fetch_one(
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
        stats_res = await services.database.fetch_all(
            "SELECT tscore, rscore, pp, plays, playtime, acc, max_combo, "
            "xh_count, x_count, sh_count, s_count, a_count FROM stats "
            "WHERE id = :userid",
            {"userid": resolved_user_id},
        )

        for idx, mode_stats in enumerate(stats_res):
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

        api_data["stats"] = stats_res

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
            row = await services.database.fetch_one(
                "SELECT latest_activity FROM users WHERE id = :id",
                {"id": username},
            )
        else:  # if user_id
            row = await services.database.fetch_one(
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
    res = await services.database.fetch_all(" ".join(query), params)

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
async def api_get_player_most_played(conn: Connection):
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
    res = await services.database.fetch_all(
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
async def api_get_map_info(conn: Connection):
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
async def api_get_map_scores(conn: Connection):
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

    res = await services.database.fetch_all(" ".join(query), params)
    return ORJSONResponse({"status": "success", "scores": res})


@router.get("/api/get_score_info")
async def api_get_score_info(conn: Connection):
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

    res = await services.database.fetch_one(
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
async def api_get_replay(conn: Connection):
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
    res = await services.database.fetch_one(
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
async def api_get_match(conn: Connection):
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
async def api_get_global_leaderboard(conn: Connection):
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

    res = await services.database.fetch_all(
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


def requires_api_key(f: Callable) -> Callable:
    @wraps(f)
    async def wrapper(conn: Connection):
        conn.resp_headers["Content-Type"] = "application/json"
        if "Authorization" not in conn.headers:
            return ORJSONResponse(
                {"status": "Must provide authorization token."},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        api_key = conn.headers["Authorization"]

        if api_key not in glob.api_keys:
            return ORJSONResponse(
                {"status": "Unknown authorization token."},
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        # get player from api token
        player_id = glob.api_keys[api_key]
        p = await glob.players.from_cache_or_sql(id=player_id)

        return await f(conn, p)

    return wrapper


# NOTE: `Content-Type = application/json` is applied in the above decorator
#                                         for the following api handlers.


@router.put("/api/set_avatar")
@requires_api_key
async def api_set_avatar(conn: Connection, p: "Player"):
    """Update the tokenholder's avatar to a given file."""
    if "avatar" not in conn.files:
        return ORJSONResponse(
            {"status": "must provide avatar file."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    ava_file = conn.files["avatar"]

    # block files over 4MB
    if len(ava_file) > (4 * 1024 * 1024):
        return ORJSONResponse(
            {"status": "avatar file too large (max 4MB)."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if ava_file[6:10] in (b"JFIF", b"Exif"):
        ext = "jpeg"
    elif ava_file.startswith(b"\211PNG\r\n\032\n"):
        ext = "png"
    else:
        return ORJSONResponse(
            {"status": "invalid file type."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # write to the avatar file
    (AVATARS_PATH / f"{p.id}.{ext}").write_bytes(ava_file)
    return ORJSONResponse({"status": "success."})


""" Misc handlers """

if glob.config.redirect_osu_urls:
    # NOTE: this will likely be removed with the addition of a frontend.
    @router.route(
        {
            re.compile(r"^/beatmapsets/\d{1,10}(?:/discussion)?/?$"),
            re.compile(r"^/beatmaps/\d{1,10}/?"),
            re.compile(r"^/community/forums/topics/\d{1,10}/?$"),
        },
    )
    async def osu_redirects(conn: Connection):
        """Redirect some common url's the client uses to osu!."""
        conn.resp_headers["Location"] = f"https://osu.ppy.sh{conn.path}"
        return (301, b"")


@router.route(re.compile(r"^/ss/[a-zA-Z0-9-_]{8}\.(png|jpeg)$"))
async def get_screenshot(conn: Connection):
    """Serve a screenshot from the server, by filename."""
    if len(conn.path) not in (16, 17):
        return (400, b"Invalid request.")

    path = SCREENSHOTS_PATH / conn.path[4:]

    if not path.exists():
        return ORJSONResponse(
            {"status": "Screenshot not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return path.read_bytes()


@router.route(re.compile(r"^/d/\d{1,10}n?$"))
async def get_osz(conn: Connection):
    """Handle a map download request (osu.ppy.sh/d/*)."""
    set_id = conn.path[3:]

    if no_video := set_id[-1] == "n":
        set_id = set_id[:-1]

    if USING_CHIMU:
        query_str = f"download/{set_id}?n={int(no_video)}"
    else:
        query_str = f"d/{set_id}"

    conn.resp_headers["Location"] = f"{glob.config.mirror}/{query_str}"
    return (301, b"")


@router.route(re.compile(r"^/web/maps/"))
async def get_updated_beatmap(conn: Connection):
    """Send the latest .osu file the server has for a given map."""
    if conn.headers["Host"] == "osu.ppy.sh":
        # server switcher, use old method
        map_filename = unquote(conn.path[10:])

        if not (
            res := await services.database.fetch_one(
                "SELECT id, md5 FROM maps WHERE filename = %s",
                [map_filename],
            )
        ):
            return (404, b"")  # map not found in sql

        osu_file_path = BEATMAPS_PATH / f'{res["id"]}.osu'

        if (
            osu_file_path.exists()
            and res["md5"] == hashlib.md5(osu_file_path.read_bytes()).hexdigest()
        ):
            # up to date map found on disk.
            content = osu_file_path.read_bytes()
        else:
            if not glob.has_internet:
                return (503, b"")  # requires internet connection

            # map not found, or out of date; get from osu!
            url = f"https://old.ppy.sh/osu/{res['id']}"

            async with glob.http_session.get(url) as resp:
                if not resp or resp.status != 200:
                    log(f"Could not find map {osu_file_path}!", Ansi.LRED)
                    return (404, b"")  # couldn't find on osu!'s server

                content = await resp.read()

            # save it to disk for future
            osu_file_path.write_bytes(content)

        return content
    else:
        # using -devserver, just redirect them to osu
        conn.resp_headers["Location"] = f"https://osu.ppy.sh{conn.path}"
        return (301, b"")


@router.route("/p/doyoureallywanttoaskpeppy")
async def peppyDMHandler(conn: Connection):
    return (
        b"This user's ID is usually peppy's (when on bancho), "
        b"and is blocked from being messaged by the osu! client."
    )


""" ingame registration """


@router.route("/users", methods=["POST"])
@ratelimit(period=300, max_count=15)  # 15 registrations / 5mins
@acquire_db_conn(aiomysql.Cursor)
async def register_account(
    conn: Connection,
    db_cursor: aiomysql.Cursor,
):
    mp_args = conn.multipart_args

    name = mp_args["user[username]"].strip()
    email = mp_args["user[user_email]"]
    pw_txt = mp_args["user[password]"]
    safe_name = safe_name = name.lower().replace(" ", "_")

    if not all((name, email, pw_txt)) or "check" not in mp_args:
        return (400, b"Missing required params")

    # ensure all args passed
    # are safe for registration.
    errors: Mapping[str, list[str]] = defaultdict(list)

    # Usernames must:
    # - be within 2-15 characters in length
    # - not contain both ' ' and '_', one is fine
    # - not be in the config's `disallowed_names` list
    # - not already be taken by another player
    if not regexes.USERNAME.match(name):
        errors["username"].append("Must be 2-15 characters in length.")

    if "_" in name and " " in name:
        errors["username"].append('May contain "_" and " ", but not both.')

    if name in glob.config.disallowed_names:
        errors["username"].append("Disallowed username; pick another.")

    if "username" not in errors:
        await db_cursor.execute("SELECT 1 FROM users WHERE safe_name = %s", [safe_name])
        if db_cursor.rowcount != 0:
            errors["username"].append("Username already taken by another player.")

    # Emails must:
    # - match the regex `^[^@\s]{1,200}@[^@\s\.]{1,30}\.[^@\.\s]{1,24}$`
    # - not already be taken by another player
    if not regexes.EMAIL.match(email):
        errors["user_email"].append("Invalid email syntax.")
    else:
        await db_cursor.execute("SELECT 1 FROM users WHERE email = %s", [email])
        if db_cursor.rowcount != 0:
            errors["user_email"].append("Email already taken by another player.")

    # Passwords must:
    # - be within 8-32 characters in length
    # - have more than 3 unique characters
    # - not be in the config's `disallowed_passwords` list
    if not 8 <= len(pw_txt) <= 32:
        errors["password"].append("Must be 8-32 characters in length.")

    if len(set(pw_txt)) <= 3:
        errors["password"].append("Must have more than 3 unique characters.")

    if pw_txt.lower() in glob.config.disallowed_passwords:
        errors["password"].append("That password was deemed too simple.")

    if errors:
        # we have errors to send back, send them back delimited by newlines.
        errors = {k: ["\n".join(v)] for k, v in errors.items()}
        errors_full = {"form_error": {"user": errors}}
        return (400, orjson.dumps(errors_full))

    if mp_args["check"] == "0":
        # the client isn't just checking values,
        # they want to register the account now.
        # make the md5 & bcrypt the md5 for sql.
        async with glob.players._lock:
            pw_md5 = hashlib.md5(pw_txt.encode()).hexdigest().encode()
            pw_bcrypt = bcrypt.hashpw(pw_md5, bcrypt.gensalt())
            glob.cache["bcrypt"][pw_bcrypt] = pw_md5  # cache result for login

            if "CF-IPCountry" in conn.headers:
                # best case, dev has enabled ip geolocation in the
                # network tab of cloudflare, so it sends the iso code.
                country_acronym = conn.headers["CF-IPCountry"]
            else:
                # backup method, get the user's ip and
                # do a db lookup to get their country.
                if "CF-Connecting-IP" in conn.headers:
                    ip_str = conn.headers["CF-Connecting-IP"]
                else:
                    # if the request has been forwarded, get the origin
                    forwards = conn.headers["X-Forwarded-For"].split(",")
                    if len(forwards) != 1:
                        ip_str = forwards[0]
                    else:
                        ip_str = conn.headers["X-Real-IP"]

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
                        geoloc = misc.utils.fetch_geoloc_db(ip)
                    else:
                        # worst case, we must do an external db lookup
                        # using a public api. (depends, `ping ip-api.com`)
                        geoloc = await misc.utils.fetch_geoloc_web(ip)

                    country_acronym = geoloc["country"]["acronym"]
                else:
                    # localhost, unknown country
                    country_acronym = "xx"

            # add to `users` table.
            await db_cursor.execute(
                "INSERT INTO users "
                "(name, safe_name, email, pw_bcrypt, country, creation_time, latest_activity) "
                "VALUES (%s, %s, %s, %s, %s, UNIX_TIMESTAMP(), UNIX_TIMESTAMP())",
                [name, safe_name, email, pw_bcrypt, country_acronym],
            )
            user_id = db_cursor.lastrowid

            # add to `stats` table.
            await db_cursor.executemany(
                "INSERT INTO stats (id, mode) VALUES (%s, %s)",
                [(user_id, mode) for mode in range(8)],
            )

        if glob.datadog:
            glob.datadog.increment("gulag.registrations")

        log(f"<{name} ({user_id})> has registered!", Ansi.LGREEN)

    return b"ok"  # success


@router.route("/difficulty-rating", methods=["POST"])
async def difficultyRatingHandler(conn: Connection) -> Optional[bytes]:
    conn.resp_headers["Location"] = f"https://osu.ppy.sh{conn.path}"
    return (307, b"")
