from __future__ import annotations

import io
from types import SimpleNamespace

import pytest
from starlette.datastructures import FormData
from starlette.datastructures import UploadFile

from app.api.domains import osu
from app.constants.beatmap_statuses import RankedStatus
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.objects.player import ModeData
from app.objects.score import Grade
from app.objects.score import Score
from app.repositories.achievements import Achievement
from app.services import osu_web
from app.services import score_submission


def _score() -> Score:
    score = Score()
    score.id = 42
    score.n300 = 83
    score.n100 = 14
    score.n50 = 5
    score.ngeki = 23
    score.nkatu = 6
    score.nmiss = 6
    score.score = 26_810
    score.max_combo = 52
    score.perfect = False
    score.grade = Grade.C
    score.mods = Mods.HIDDEN | Mods.RELAX
    score.passed = True
    score.mode = GameMode.RELAX_OSU
    score.time_elapsed = 13_358
    score.acc = 81.94
    score.pp = 10.448
    score.rank = 1
    score.prev_best = None
    score.player = SimpleNamespace(id=6, name="test-user", restricted=False)
    score.bmap = SimpleNamespace(
        id=315,
        set_id=141,
        plays=1,
        passes=1,
        last_update="2014-05-18 15:41:48",
        status=RankedStatus.Ranked,
        has_leaderboard=True,
        awards_ranked_pp=True,
        embed="[https://osu.cmyui.xyz/b/315 test map]",
        set=SimpleNamespace(url="https://osu.cmyui.xyz/s/141"),
    )
    return score


def _stats() -> tuple[ModeData, ModeData]:
    previous = ModeData(
        tscore=0,
        rscore=0,
        pp=0,
        acc=0.0,
        plays=0,
        playtime=0,
        max_combo=0,
        total_hits=0,
        rank=0,
        grades={},
    )
    current = ModeData(
        tscore=26_810,
        rscore=26_810,
        pp=11,
        acc=81.94,
        plays=1,
        playtime=13,
        max_combo=52,
        total_hits=102,
        rank=1,
        grades={},
    )
    return previous, current


def test_parse_score_form_data_returns_score_bytes_and_replay_file() -> None:
    replay_file = UploadFile(filename="score.osr", file=io.BytesIO(b"replay"))
    form_data = FormData(
        [
            ("score", "encrypted-score"),
            ("score", replay_file),
        ],
    )

    parsed = osu.parse_form_data_score_params(form_data)

    assert parsed == (b"encrypted-score", replay_file)


@pytest.mark.parametrize(
    "form_data",
    [
        FormData([("score", "encrypted-score")]),
        FormData(
            [
                ("score", "encrypted-score"),
                ("score", "not-a-file"),
            ],
        ),
    ],
)
def test_parse_score_form_data_rejects_invalid_score_parts(
    form_data: FormData,
) -> None:
    assert osu.parse_form_data_score_params(form_data) is None


def test_chart_entry_formats_optional_before_and_after_values() -> None:
    assert osu.chart_entry("rankedScore", None, 123.45) == (
        "rankedScoreBefore:|rankedScoreAfter:123.45"
    )


def test_format_achievement_string_uses_client_delimiters() -> None:
    assert (
        osu.format_achievement_string(
            "osu-combo-500",
            "500 Combo",
            "Achieve a 500 combo.",
        )
        == "osu-combo-500+500 Combo+Achieve a 500 combo."
    )


def test_build_submission_charts_formats_osu_client_response() -> None:
    score = _score()
    previous_stats, current_stats = _stats()
    achievements: list[Achievement] = [
        {
            "id": 1,
            "file": "osu-skill-pass-4",
            "name": "Insanity Approaches",
            "desc": "You're not twitching, you're just ready.",
            "cond": lambda score, mode_vn: True,
        },
        {
            "id": 2,
            "file": "all-intro-hidden",
            "name": "Blindsight",
            "desc": "I can see just perfectly",
            "cond": lambda score, mode_vn: True,
        },
    ]

    response = osu.build_submission_charts(
        score=score,
        previous_stats=previous_stats,
        current_stats=current_stats,
        achievements=achievements,
        domain="cmyui.xyz",
    )

    assert response == (
        b"beatmapId:315|beatmapSetId:141|beatmapPlaycount:1|beatmapPasscount:1|approvedDate:2014-05-18 15:41:48|\n"
        b"|chartId:beatmap|chartUrl:https://osu.cmyui.xyz/s/141|chartName:Beatmap Ranking|rankBefore:|rankAfter:1|rankedScoreBefore:|rankedScoreAfter:26810|totalScoreBefore:|totalScoreAfter:26810|maxComboBefore:|maxComboAfter:52|accuracyBefore:|accuracyAfter:81.94|ppBefore:|ppAfter:10.448|onlineScoreId:42|\n"
        b"|chartId:overall|chartUrl:https://cmyui.xyz/u/6|chartName:Overall Ranking|rankBefore:|rankAfter:1|rankedScoreBefore:|rankedScoreAfter:26810|totalScoreBefore:|totalScoreAfter:26810|maxComboBefore:|maxComboAfter:52|accuracyBefore:|accuracyAfter:81.94|ppBefore:|ppAfter:11|achievements-new:osu-skill-pass-4+Insanity Approaches+You're not twitching, you're just ready./all-intro-hidden+Blindsight+I can see just perfectly"
    )


def test_build_submission_charts_includes_previous_best_values() -> None:
    score = _score()
    previous_best = Score()
    previous_best.rank = 4
    previous_best.score = 20_000
    previous_best.max_combo = 40
    previous_best.acc = 80.123
    previous_best.pp = 9.5
    score.prev_best = previous_best
    previous_stats, current_stats = _stats()

    response = osu.build_submission_charts(
        score=score,
        previous_stats=previous_stats,
        current_stats=current_stats,
        achievements=[],
        domain="cmyui.xyz",
    )

    assert (
        b"rankBefore:4|rankAfter:1|rankedScoreBefore:20000|rankedScoreAfter:26810"
        in response
    )
    assert (
        b"accuracyBefore:80.12|accuracyAfter:81.94|ppBefore:9.5|ppAfter:10.448"
        in response
    )


def test_build_score_submission_response_returns_error_for_failed_score() -> None:
    score = _score()
    score.passed = False
    previous_stats, current_stats = _stats()

    response = osu.build_score_submission_response(
        score=score,
        previous_stats=previous_stats,
        current_stats=current_stats,
        domain="cmyui.xyz",
        unlocked_achievements=[],
    )

    assert response == b"error: no"


def test_build_score_submission_response_formats_empty_achievements() -> None:
    score = _score()
    previous_stats, current_stats = _stats()

    response = osu.build_score_submission_response(
        score=score,
        previous_stats=previous_stats,
        current_stats=current_stats,
        domain="cmyui.xyz",
        unlocked_achievements=[],
    )

    assert b"achievements-new:" in response
    assert b"osu-skill-pass-4" not in response


def test_build_score_submission_response_formats_unlocked_achievements() -> None:
    score = _score()
    previous_stats, current_stats = _stats()
    achievements: list[Achievement] = [
        {
            "id": 1,
            "file": "osu-skill-pass-4",
            "name": "Insanity Approaches",
            "desc": "You're not twitching, you're just ready.",
            "cond": lambda score, mode_vn: True,
        },
    ]

    response = osu.build_score_submission_response(
        score=score,
        previous_stats=previous_stats,
        current_stats=current_stats,
        domain="cmyui.xyz",
        unlocked_achievements=achievements,
    )

    assert (
        b"achievements-new:osu-skill-pass-4+Insanity Approaches+You're not twitching, you're just ready."
        in response
    )


@pytest.mark.parametrize(
    ("error_code", "expected_response"),
    [
        (
            score_submission.ScoreSubmissionErrorCode.BEATMAP_NOT_FOUND,
            b"error: beatmap",
        ),
        (score_submission.ScoreSubmissionErrorCode.PLAYER_NOT_FOUND, b""),
        (score_submission.ScoreSubmissionErrorCode.DUPLICATE_SUBMISSION, b"error: no"),
    ],
)
def test_build_score_submission_error_response_maps_domain_errors_to_osu_protocol(
    error_code: score_submission.ScoreSubmissionErrorCode,
    expected_response: bytes,
) -> None:
    error = score_submission.ScoreSubmissionError(code=error_code)

    assert osu.build_score_submission_error_response(error) == expected_response


def test_format_scores_response_formats_personal_best_and_leaderboard_rows() -> None:
    response = osu.format_scores_response(
        osu_web.OsuLeaderboardResult(
            code=osu_web.OsuLeaderboardResultCode.FOUND,
            ranked_status=RankedStatus.Ranked,
            beatmap_id=321,
            beatmap_set_id=654,
            beatmap_name="Artist - Title [Hard]",
            beatmap_rating=9.5,
            score_rows=[
                {
                    "id": 10,
                    "leaderboard_value": 987.6,
                    "max_combo": 321,
                    "n50": 1,
                    "n100": 2,
                    "n300": 300,
                    "nmiss": 0,
                    "nkatu": 4,
                    "ngeki": 5,
                    "perfect": 1,
                    "mods": Mods.HIDDEN.value,
                    "time": 1_704_110_400,
                    "userid": 7,
                    "name": "leaderboard-user",
                },
            ],
            personal_best_score_row={
                "id": 11,
                "leaderboard_value": 543.2,
                "max_combo": 123,
                "n50": 1,
                "n100": 2,
                "n300": 300,
                "nmiss": 0,
                "nkatu": 4,
                "ngeki": 5,
                "perfect": 1,
                "mods": Mods.HIDDEN.value,
                "time": 1_704_110_400,
                "rank": 4,
            },
            personal_best_user_id=6,
            personal_best_display_name="[AK] cmyui",
        ),
    )

    assert response == (
        b"2|false|321|654|1|0|\n"
        b"0\nArtist - Title [Hard]\n9.5\n"
        b"11|[AK] cmyui|543|123|1|2|300|0|4|5|1|8|6|4|1704110400|1\n"
        b"10|leaderboard-user|988|321|1|2|300|0|4|5|1|8|7|1|1704110400|1"
    )
