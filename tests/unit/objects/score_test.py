from __future__ import annotations

from datetime import datetime

import pytest

from app.constants.clientflags import ClientFlags
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.objects.score import Grade
from app.objects.score import Score


def _score(
    *,
    mode: GameMode,
    mods: Mods = Mods.NOMOD,
    n300: int = 0,
    n100: int = 0,
    n50: int = 0,
    ngeki: int = 0,
    nkatu: int = 0,
    nmiss: int = 0,
) -> Score:
    score = Score()
    score.mode = mode
    score.mods = mods
    score.n300 = n300
    score.n100 = n100
    score.n50 = n50
    score.ngeki = ngeki
    score.nkatu = nkatu
    score.nmiss = nmiss
    return score


def test_from_submission_parses_stable_score_payload() -> None:
    score = Score.from_submission(
        [
            "online-checksum",
            "300",
            "25",
            "5",
            "50",
            "10",
            "2",
            "987654",
            "512",
            "True",
            "SH",
            str(int(Mods.HIDDEN | Mods.RELAX)),
            "True",
            str(GameMode.VANILLA_OSU.value),
            "240102030405",
            "20240102       ",
        ],
    )

    assert score.client_checksum == "online-checksum"
    assert score.n300 == 300
    assert score.n100 == 25
    assert score.n50 == 5
    assert score.ngeki == 50
    assert score.nkatu == 10
    assert score.nmiss == 2
    assert score.score == 987_654
    assert score.max_combo == 512
    assert score.perfect is True
    assert score.grade is Grade.SH
    assert score.mods == Mods.HIDDEN | Mods.RELAX
    assert score.passed is True
    assert score.mode is GameMode.RELAX_OSU
    assert score.client_time == datetime(2024, 1, 2, 3, 4, 5)
    assert score.client_flags == ClientFlags(3)


@pytest.mark.parametrize(
    ("score", "expected_accuracy"),
    [
        (
            _score(
                mode=GameMode.VANILLA_OSU,
                n300=300,
                n100=25,
                n50=5,
                nmiss=2,
            ),
            100.0 * ((300 * 300.0) + (25 * 100.0) + (5 * 50.0)) / (332 * 300.0),
        ),
        (
            _score(
                mode=GameMode.VANILLA_TAIKO,
                n300=300,
                n100=25,
                nmiss=2,
            ),
            100.0 * ((25 * 0.5) + 300) / 327,
        ),
        (
            _score(
                mode=GameMode.VANILLA_CATCH,
                n300=300,
                n100=25,
                n50=5,
                nkatu=10,
                nmiss=2,
            ),
            100.0 * (300 + 25 + 5) / 342,
        ),
        (
            _score(
                mode=GameMode.VANILLA_MANIA,
                n300=300,
                n100=25,
                n50=5,
                ngeki=50,
                nkatu=10,
                nmiss=2,
            ),
            100.0
            * ((5 * 50.0) + (25 * 100.0) + (10 * 200.0) + ((300 + 50) * 300.0))
            / (392 * 300.0),
        ),
        (
            _score(
                mode=GameMode.VANILLA_MANIA,
                mods=Mods.SCOREV2,
                n300=300,
                n100=25,
                n50=5,
                ngeki=50,
                nkatu=10,
                nmiss=2,
            ),
            100.0
            * ((5 * 50.0) + (25 * 100.0) + (10 * 200.0) + (300 * 300.0) + (50 * 305.0))
            / (392 * 305.0),
        ),
    ],
)
def test_calculate_accuracy_matches_stable_rulesets(
    score: Score,
    expected_accuracy: float,
) -> None:
    assert score.calculate_accuracy() == pytest.approx(expected_accuracy)


@pytest.mark.parametrize(
    "mode",
    [
        GameMode.VANILLA_OSU,
        GameMode.VANILLA_TAIKO,
        GameMode.VANILLA_CATCH,
        GameMode.VANILLA_MANIA,
    ],
)
def test_calculate_accuracy_returns_zero_for_empty_submission(mode: GameMode) -> None:
    assert _score(mode=mode).calculate_accuracy() == 0.0
