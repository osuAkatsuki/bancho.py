from __future__ import annotations

from datetime import datetime

from app.constants.beatmap_statuses import RankedStatus
from app.constants.gamemodes import GameMode
from app.objects.beatmap import Beatmap
from app.objects.beatmap import BeatmapSet


def _osuapi_beatmap_response(**overrides: object) -> dict[str, object]:
    response: dict[str, object] = {
        "approved": "1",
        "artist": "Camellia",
        "beatmap_id": "42",
        "beatmapset_id": "141",
        "bpm": "180.5",
        "creator": "cmyui",
        "diff_approach": "9.5",
        "diff_drain": "6.5",
        "diff_overall": "8.5",
        "diff_size": "4.0",
        "difficultyrating": "5.25",
        "file_md5": "60b725f10c9c85c70d97880dfe8191b3",
        "last_update": "2024-01-02 03:04:05",
        "max_combo": "1234",
        "mode": "0",
        "title": "Exit This Earth's Atomosphere",
        "total_length": "215",
        "version": "Another",
    }
    response.update(overrides)
    return response


def test_from_osuapi_response_initializes_beatmap() -> None:
    beatmap_set = BeatmapSet(id=141, last_osuapi_check=datetime(2024, 1, 1))

    beatmap = Beatmap.from_osuapi_response(
        _osuapi_beatmap_response(),
        map_set=beatmap_set,
    )

    assert beatmap.set is beatmap_set
    assert beatmap.id == 42
    assert beatmap.set_id == 141
    assert beatmap.md5 == "60b725f10c9c85c70d97880dfe8191b3"
    assert beatmap.full_name == "Camellia - Exit This Earth's Atomosphere [Another]"
    assert (
        beatmap.filename
        == "Camellia - Exit This Earth's Atomosphere (cmyui) [Another].osu"
    )
    assert beatmap.last_update == datetime(2024, 1, 2, 3, 4, 5)
    assert beatmap.total_length == 215
    assert beatmap.max_combo == 1234
    assert beatmap.status is RankedStatus.Ranked
    assert beatmap.mode is GameMode.VANILLA_OSU
    assert beatmap.bpm == 180.5
    assert beatmap.cs == 4.0
    assert beatmap.od == 8.5
    assert beatmap.ar == 9.5
    assert beatmap.hp == 6.5
    assert beatmap.diff == 5.25
    assert beatmap.frozen is False
    assert beatmap.plays == 0
    assert beatmap.passes == 0


def test_update_from_osuapi_response_preserves_frozen_status() -> None:
    beatmap_set = BeatmapSet(id=141, last_osuapi_check=datetime(2024, 1, 1))
    beatmap = Beatmap.from_osuapi_response(
        _osuapi_beatmap_response(),
        map_set=beatmap_set,
        frozen=True,
        status=RankedStatus.Loved,
        plays=12,
        passes=4,
    )

    beatmap.update_from_osuapi_response(
        _osuapi_beatmap_response(
            approved="0",
            file_md5="438c997a149c1c74fd7769a6134ec16d",
            max_combo=None,
            version="Updated",
        ),
    )

    assert beatmap.status is RankedStatus.Loved
    assert beatmap.md5 == "438c997a149c1c74fd7769a6134ec16d"
    assert beatmap.version == "Updated"
    assert beatmap.max_combo == 0
    assert beatmap.plays == 12
    assert beatmap.passes == 4
