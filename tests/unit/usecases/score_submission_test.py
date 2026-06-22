from __future__ import annotations

import hashlib
from datetime import date
from datetime import datetime
from ipaddress import IPv4Address
from types import SimpleNamespace

import pytest

from app.constants.clientflags import ClientFlags
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.objects.player import ClientDetails
from app.objects.player import ModeData
from app.objects.player import OsuStream
from app.objects.player import OsuVersion
from app.objects.score import Grade
from app.objects.score import Score
from app.usecases import score_submission


def _md5(value: str) -> str:
    return hashlib.md5(value.encode()).hexdigest()


def _client_details() -> ClientDetails:
    return ClientDetails(
        osu_version=OsuVersion(
            date=date(2024, 1, 2),
            revision=None,
            stream=OsuStream.STABLE,
        ),
        osu_path_md5="osu-path",
        adapters_md5="adapters",
        uninstall_md5=_md5("unique1"),
        disk_signature_md5=_md5("unique2"),
        adapters=["adapter1", "adapter2"],
        ip=IPv4Address("127.0.0.1"),
    )


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
    score.client_time = datetime(2024, 1, 1, 12, 0, 0)
    score.server_time = score.client_time
    score.time_elapsed = 13_358
    score.client_flags = ClientFlags(0)
    score.acc = 81.94
    score.pp = 10.448
    score.rank = 1
    score.prev_best = None
    score.client_checksum = ""
    score.player = SimpleNamespace(id=6, name="test-user", restricted=False)
    score.bmap = SimpleNamespace(
        id=315,
        set_id=141,
        md5="1cf5b2c2edfafd055536d2cefcb89c0e",
        plays=1,
        passes=1,
        last_update="2014-05-18 15:41:48",
        awards_ranked_pp=True,
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


class _FailingAchievements:
    async def fetch_many(self) -> list[dict[str, object]]:
        raise AssertionError("achievements should not be fetched")


class _FailingUserAchievements:
    async def fetch_many(
        self,
        *,
        user_id: int,
    ) -> list[dict[str, int]]:
        raise AssertionError("user achievements should not be fetched")

    async def create(
        self,
        user_id: int,
        achievement_id: int,
    ) -> dict[str, int]:
        raise AssertionError("user achievements should not be created")


class _FakeAchievements:
    async def fetch_many(self) -> list[dict[str, object]]:
        return [
            {
                "id": 1,
                "file": "osu-skill-pass-4",
                "name": "Insanity Approaches",
                "desc": "You're not twitching, you're just ready.",
                "cond": lambda score, mode_vn: True,
            },
            {
                "id": 2,
                "file": "osu-combo-500",
                "name": "500 Combo",
                "desc": "Achieve a 500 combo.",
                "cond": lambda score, mode_vn: False,
            },
            {
                "id": 3,
                "file": "all-intro-hidden",
                "name": "Blindsight",
                "desc": "I can see just perfectly",
                "cond": lambda score, mode_vn: True,
            },
        ]


class _FakeUserAchievements:
    def __init__(self) -> None:
        self.created_achievement_ids: list[int] = []

    async def fetch_many(
        self,
        *,
        user_id: int,
    ) -> list[dict[str, int]]:
        assert user_id == 6
        return [{"userid": 6, "achid": 3}]

    async def create(
        self,
        user_id: int,
        achievement_id: int,
    ) -> dict[str, int]:
        assert user_id == 6
        self.created_achievement_ids.append(achievement_id)
        return {"userid": user_id, "achid": achievement_id}


def test_parse_unique_id_hashes_md5s_submission_unique_ids() -> None:
    unique_id_hashes = score_submission.parse_unique_id_hashes("unique1|unique2")

    assert unique_id_hashes == score_submission.UniqueIdHashes(
        unique_id1_md5=_md5("unique1"),
        unique_id2_md5=_md5("unique2"),
    )


def test_chart_entry_formats_optional_before_and_after_values() -> None:
    assert score_submission.chart_entry("rankedScore", None, 123.45) == (
        "rankedScoreBefore:|rankedScoreAfter:123.45"
    )


def test_format_achievement_string_uses_client_delimiters() -> None:
    assert (
        score_submission.format_achievement_string(
            "osu-combo-500",
            "500 Combo",
            "Achieve a 500 combo.",
        )
        == "osu-combo-500+500 Combo+Achieve a 500 combo."
    )


def test_validate_client_details_accepts_matching_login_and_submission_data() -> None:
    client_details = _client_details()

    score_submission.validate_client_details(
        client_details=client_details,
        osu_version="20240102",
        client_hash=client_details.client_hash,
        unique_id_hashes=score_submission.parse_unique_id_hashes("unique1|unique2"),
    )


def test_validate_client_details_rejects_missing_client_details() -> None:
    with pytest.raises(ValueError, match="missing client details"):
        score_submission.validate_client_details(
            client_details=None,
            osu_version="20240102",
            client_hash="client-hash",
            unique_id_hashes=score_submission.parse_unique_id_hashes("unique1|unique2"),
        )


@pytest.mark.parametrize(
    ("osu_version", "client_hash", "unique_ids", "expected_error"),
    [
        ("20240101", None, "unique1|unique2", "osu! version mismatch"),
        ("20240102", "wrong-hash", "unique1|unique2", "client hash mismatch"),
        ("20240102", None, "wrong|unique2", "unique_id1 mismatch"),
        ("20240102", None, "unique1|wrong", "unique_id2 mismatch"),
    ],
)
def test_validate_client_details_rejects_mismatched_submission_data(
    osu_version: str,
    client_hash: str | None,
    unique_ids: str,
    expected_error: str,
) -> None:
    client_details = _client_details()
    if client_hash is None:
        client_hash = client_details.client_hash

    with pytest.raises(ValueError, match=expected_error):
        score_submission.validate_client_details(
            client_details=client_details,
            osu_version=osu_version,
            client_hash=client_hash,
            unique_id_hashes=score_submission.parse_unique_id_hashes(unique_ids),
        )


def test_validate_submission_integrity_accepts_matching_submission_data() -> None:
    client_details = _client_details()
    score = _score()
    score.client_checksum = score.compute_online_checksum(
        osu_version="20240102",
        osu_client_hash=client_details.client_hash,
        storyboard_checksum="storyboard",
    )

    score_submission.validate_submission_integrity(
        client_details=client_details,
        osu_version="20240102",
        client_hash=client_details.client_hash,
        unique_ids="unique1|unique2",
        score=score,
        storyboard_md5="storyboard",
        submission_beatmap_md5="1cf5b2c2edfafd055536d2cefcb89c0e",
        updated_beatmap_hash="1cf5b2c2edfafd055536d2cefcb89c0e",
    )


def test_validate_submission_integrity_rejects_mismatched_score_checksum() -> None:
    client_details = _client_details()
    score = _score()
    score.client_checksum = "wrong-checksum"

    with pytest.raises(ValueError, match="online score checksum mismatch"):
        score_submission.validate_submission_integrity(
            client_details=client_details,
            osu_version="20240102",
            client_hash=client_details.client_hash,
            unique_ids="unique1|unique2",
            score=score,
            storyboard_md5="storyboard",
            submission_beatmap_md5="1cf5b2c2edfafd055536d2cefcb89c0e",
            updated_beatmap_hash="1cf5b2c2edfafd055536d2cefcb89c0e",
        )


def test_validate_submission_integrity_rejects_mismatched_beatmap_hash() -> None:
    client_details = _client_details()
    score = _score()
    score.client_checksum = score.compute_online_checksum(
        osu_version="20240102",
        osu_client_hash=client_details.client_hash,
        storyboard_checksum="storyboard",
    )

    with pytest.raises(ValueError, match="beatmap hash mismatch"):
        score_submission.validate_submission_integrity(
            client_details=client_details,
            osu_version="20240102",
            client_hash=client_details.client_hash,
            unique_ids="unique1|unique2",
            score=score,
            storyboard_md5="storyboard",
            submission_beatmap_md5="1cf5b2c2edfafd055536d2cefcb89c0e",
            updated_beatmap_hash="wrong-md5",
        )


def test_build_submission_charts_formats_osu_client_response() -> None:
    score = _score()
    previous_stats, current_stats = _stats()
    achievements = [
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

    response = score_submission.build_submission_charts(
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

    response = score_submission.build_submission_charts(
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


async def test_build_score_submission_response_returns_error_for_failed_score() -> None:
    score = _score()
    score.passed = False
    previous_stats, current_stats = _stats()

    response = await score_submission.build_score_submission_response(
        score=score,
        previous_stats=previous_stats,
        current_stats=current_stats,
        domain="cmyui.xyz",
        achievements=_FailingAchievements(),
        user_achievements=_FailingUserAchievements(),
    )

    assert response == b"error: no"


@pytest.mark.parametrize(
    ("awards_ranked_pp", "restricted"),
    [
        (False, False),
        (True, True),
    ],
)
async def test_build_score_submission_response_skips_achievements_when_score_is_not_eligible(
    awards_ranked_pp: bool,
    restricted: bool,
) -> None:
    score = _score()
    score.bmap.awards_ranked_pp = awards_ranked_pp
    score.player.restricted = restricted
    previous_stats, current_stats = _stats()

    response = await score_submission.build_score_submission_response(
        score=score,
        previous_stats=previous_stats,
        current_stats=current_stats,
        domain="cmyui.xyz",
        achievements=_FailingAchievements(),
        user_achievements=_FailingUserAchievements(),
    )

    assert b"achievements-new:" in response
    assert b"osu-skill-pass-4" not in response


async def test_build_score_submission_response_unlocks_matching_new_achievements() -> (
    None
):
    score = _score()
    previous_stats, current_stats = _stats()
    user_achievements = _FakeUserAchievements()

    response = await score_submission.build_score_submission_response(
        score=score,
        previous_stats=previous_stats,
        current_stats=current_stats,
        domain="cmyui.xyz",
        achievements=_FakeAchievements(),
        user_achievements=user_achievements,
    )

    assert user_achievements.created_achievement_ids == [1]
    assert (
        b"achievements-new:osu-skill-pass-4+Insanity Approaches+You're not twitching, you're just ready."
        in response
    )
    assert b"osu-combo-500" not in response
    assert b"all-intro-hidden" not in response
