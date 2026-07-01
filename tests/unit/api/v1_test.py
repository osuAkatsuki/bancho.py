from __future__ import annotations

from datetime import datetime

import app.api.v1.api as v1_api
from app.objects.beatmap import Beatmap
from app.objects.beatmap import BeatmapSet
from app.repositories.scores import PlayerScoreListingRow
from app.services.performance import DifficultyRating
from app.services.performance import PerformanceRating
from app.services.performance import PerformanceResult
from app.services.scores import PlayerScoreWithBeatmap


def test_format_performance_result_preserves_v1_response_shape() -> None:
    result = PerformanceResult(
        performance=PerformanceRating(
            pp=123.456,
            pp_acc=1.0,
            pp_aim=2.0,
            pp_speed=3.0,
            pp_flashlight=4.0,
            effective_miss_count=5.0,
            pp_difficulty=6.0,
        ),
        difficulty=DifficultyRating(
            stars=7.0,
            aim=8.0,
            speed=9.0,
            flashlight=10.0,
            slider_factor=11.0,
            speed_note_count=12.0,
            stamina=13.0,
            color=14.0,
            rhythm=15.0,
            peak=16.0,
        ),
    )

    assert v1_api.format_performance_result(result, accuracy=98.76) == {
        "performance": {
            "pp": 123.456,
            "pp_acc": 1.0,
            "pp_aim": 2.0,
            "pp_speed": 3.0,
            "pp_flashlight": 4.0,
            "effective_miss_count": 5.0,
            "pp_difficulty": 6.0,
        },
        "difficulty": {
            "stars": 7.0,
            "aim": 8.0,
            "speed": 9.0,
            "flashlight": 10.0,
            "slider_factor": 11.0,
            "speed_note_count": 12.0,
            "stamina": 13.0,
            "color": 14.0,
            "rhythm": 15.0,
            "peak": 16.0,
        },
        "accuracy": 98.76,
    }


def test_format_player_score_with_beatmap_preserves_v1_response_shape() -> None:
    play_time = datetime(2024, 1, 1)
    beatmap = Beatmap(
        map_set=BeatmapSet(id=2, last_osuapi_check=datetime(2024, 1, 1)),
        md5="map-md5",
        id=1,
        set_id=2,
        artist="Artist",
        title="Title",
        version="Hard",
        creator="creator",
    )
    score = PlayerScoreListingRow(
        id=3,
        map_md5="map-md5",
        score=1_000_000,
        pp=123.45,
        acc=98.76,
        max_combo=321,
        mods=8,
        n300=300,
        n100=5,
        n50=1,
        nmiss=0,
        ngeki=0,
        nkatu=0,
        grade="A",
        status=2,
        mode=4,
        play_time=play_time,
        time_elapsed=60_000,
        perfect=1,
    )

    assert v1_api.format_player_score_with_beatmap(
        PlayerScoreWithBeatmap(score=score, beatmap=beatmap),
    ) == {
        "id": 3,
        "score": 1_000_000,
        "pp": 123.45,
        "acc": 98.76,
        "max_combo": 321,
        "mods": 8,
        "n300": 300,
        "n100": 5,
        "n50": 1,
        "nmiss": 0,
        "ngeki": 0,
        "nkatu": 0,
        "grade": "A",
        "status": 2,
        "mode": 4,
        "play_time": play_time,
        "time_elapsed": 60_000,
        "perfect": 1,
        "beatmap": beatmap.as_dict,
    }
