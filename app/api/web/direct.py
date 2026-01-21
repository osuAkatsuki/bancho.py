from __future__ import annotations

from typing import Any

from fastapi import status
from fastapi.param_functions import Depends
from fastapi.param_functions import Query
from fastapi.responses import Response
from fastapi.routing import APIRouter

import app.settings
import app.state
from app.api.web.authentication import authenticate_player_session
from app.objects.beatmap import RankedStatus
from app.objects.player import Player

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


router = APIRouter()


@router.get("/osu-search.php")
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
@router.get("/osu-search-set.php")
async def osuSearchSetHandler(
    player: Player = Depends(authenticate_player_session(Query, "u", "h")),
    map_set_id: int | None = Query(None, alias="s"),
    map_id: int | None = Query(None, alias="b"),
    checksum: str | None = Query(None, alias="c"),
) -> Response:
    # Since we only need set-specific data, we can basically
    # just do same query with either bid or bsid.

    v: int | str
    if map_set_id is not None:
        # this is just a normal request
        k, v = ("set_id", map_set_id)
    elif map_id is not None:
        k, v = ("id", map_id)
    elif checksum is not None:
        k, v = ("md5", checksum)
    else:
        return Response(b"")  # invalid args

    # Get all set data.
    bmapset = await app.state.services.database.fetch_one(
        "SELECT DISTINCT set_id, artist, "
        "title, status, creator, last_update "
        f"FROM maps WHERE {k} = :v",
        {"v": v},
    )
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
