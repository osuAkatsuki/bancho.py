from __future__ import annotations

from typing import Optional

from fastapi import status

import app.settings
import app.state.services
from app.objects.beatmap import RankedStatus

# bancho.py supports both cheesegull mirrors & chimu.moe.
# chimu.moe handles things a bit differently than cheesegull,
# and has some extra features we'll eventually use more of.
USING_CHIMU = "chimu.moe" in app.settings.MIRROR_URL
USING_MINO = "catboy.best" in app.settings.MIRROR_URL

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


def get_mapset_download_url(map_set_id: int, no_video: bool) -> str:
    if USING_CHIMU:
        query_str = f"download/{map_set_id}?n={int(not no_video)}"
    else:
        query_str = f"d/{map_set_id}"
        if USING_MINO and no_video:
            query_str += "n"

    return f"{app.settings.MIRROR_URL}/{query_str}"


def get_mapset_update_url(map_filename: str) -> str:
    return f"https://osu.ppy.sh/web/maps/{map_filename}"


async def search(
    query: str,
    mode: int,
    ranked_status: int,
    page_num: int,
) -> bytes:
    if USING_CHIMU:
        search_url = f"{app.settings.MIRROR_URL}/search"
    else:
        search_url = f"{app.settings.MIRROR_URL}/api/search"

    params: dict[str, object] = {}

    # eventually we could try supporting these,
    # but it mostly depends on the mirror.
    if query not in ("Newest", "Top+Rated", "Most+Played"):
        params["query"] = query

    if mode != -1:  # -1 for all
        params["mode"] = mode

    if ranked_status != 4:  # 4 for all
        # convert to osu!api status
        params["status"] = RankedStatus.from_osudirect(ranked_status).osu_api

    if USING_MINO:
        params["raw"] = 1
        params["amount"] = 101
        params["offset"] = page_num
    else:
        params["amount"] = 100
        params["offset"] = page_num * 100

    async with app.state.services.http_client.get(search_url, params=params) as resp:
        if resp.status != status.HTTP_200_OK:
            if USING_CHIMU:
                # chimu uses 404 for no maps found
                if resp.status == status.HTTP_404_NOT_FOUND:
                    return b"0"

            return b"-1\nFailed to retrieve data from the beatmap mirror."

        if USING_MINO:
            # fastpath - mino supports formatting for return from osu!direct
            return await resp.read()

        result = await resp.json()

    if USING_CHIMU:
        if result["code"] != 0:
            return b"-1\nFailed to retrieve data from the beatmap mirror."

        result = result["data"]

    lresult = len(result)  # send over 100 if we receive
    # 100 matches, so the client
    # knows there are more to get
    ret = ["101" if lresult == 100 else str(lresult)]

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


async def search_set(
    map_id: Optional[int],
    map_set_id: Optional[int],
) -> Optional[bytes]:

    # Since we only need set-specific data, we can basically
    # just do same same query with either bid or bsid.

    if map_set_id is not None:
        # this is just a normal request
        k, v = ("set_id", map_set_id)
    elif map_id is not None:
        k, v = ("id", map_id)
    else:
        return None  # invalid args

    # Get all set data.
    # TODO: video support (needs db change)
    bmapset = await app.state.services.database.fetch_one(
        "SELECT DISTINCT set_id, artist, "
        "title, status, creator, last_update "
        f"FROM maps WHERE {k} = :v",
        {"v": v},
    )

    if bmapset is None:
        # TODO: support for other mirrors
        if USING_MINO:
            search_url = f"{app.settings.MIRROR_URL}/api/search/set"
            params: dict[str, int] = {"raw": 1}

            if map_set_id is not None:
                params["s"] = map_set_id
            elif map_id is not None:
                params["b"] = map_id

            async with app.state.services.http_client.get(
                search_url,
                params=params,
            ) as resp:
                if resp.status != status.HTTP_200_OK:
                    return None

                return await resp.read()
        else:
            return None

    return (
        (
            "{set_id}.osz|{artist}|{title}|{creator}|"
            "{status}|10.0|{last_update}|{set_id}|"  # TODO: rating
            "0|0|0|0|0"  # 0s are threadid, has_vid, has_story, filesize, filesize_novid
        )
        .format(**bmapset)
        .encode()
    )
