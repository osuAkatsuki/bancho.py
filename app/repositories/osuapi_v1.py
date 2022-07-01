from __future__ import annotations

import logging
from typing import Optional
from typing import TypedDict
from typing import Union

import app.settings
import app.state.services

# TODO: move to models?
class OsuAPIV1BeatmapResponse(TypedDict):
    """\
    A typed dictionary representing a beatmap from the v1 osu! API.

    https://github.com/ppy/osu-api/wiki#apiget_beatmaps
    """

    beatmapset_id: str
    beatmap_id: str
    approved: str
    total_length: str
    hit_length: str
    version: str
    file_md5: str
    diff_size: str
    diff_overall: str
    diff_approach: str
    diff_drain: str
    mode: str
    count_normal: str
    count_slider: str
    count_spinner: str
    submit_date: str
    approved_date: str
    last_update: str
    artist: str
    artist_unicode: str
    title: str
    title_unicode: str
    creator: str
    creator_id: str
    bpm: str
    source: str
    tags: str
    genre_id: str
    language_id: str
    favourite_count: str
    rating: str
    storyboard: str
    video: str
    download_unavailable: str
    audio_unavailable: str
    playcount: str
    passcount: str
    packs: str
    max_combo: str
    diff_aim: str
    diff_speed: str
    difficultyrating: str


async def get_beatmaps(
    **params: Union[str, int],
) -> Optional[list[OsuAPIV1BeatmapResponse]]:
    """\
    Fetch data from the osu!api with a beatmap's md5.

    https://github.com/ppy/osu-api/wiki#apiget_beatmaps
    """
    logging.debug(f"Doing osu!api (getbeatmaps) request {params}")

    if not app.settings.OSU_API_KEY:
        return None

    params["k"] = str(app.settings.OSU_API_KEY)

    async with app.state.services.http_client.get(
        url="https://old.ppy.sh/api/get_beatmaps",
        params=params,
    ) as resp:
        if resp and resp.status == 200:
            return await resp.json()

    return None
