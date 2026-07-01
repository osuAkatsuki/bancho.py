from __future__ import annotations

import pytest

from app.constants.mods import Mods


@pytest.mark.parametrize(
    ("mods", "mode_vn", "expected"),
    [
        (
            Mods.DOUBLETIME | Mods.NIGHTCORE,
            0,
            Mods.NIGHTCORE,
        ),
        (
            Mods.DOUBLETIME | Mods.HALFTIME,
            0,
            Mods.DOUBLETIME,
        ),
        (
            Mods.EASY | Mods.HARDROCK,
            0,
            Mods.EASY,
        ),
        (
            Mods.NOFAIL | Mods.SUDDENDEATH | Mods.PERFECT,
            0,
            Mods.NOFAIL,
        ),
        (
            Mods.RELAX | Mods.NOFAIL,
            0,
            Mods.RELAX,
        ),
        (
            Mods.AUTOPILOT | Mods.SPUNOUT,
            0,
            Mods.SPUNOUT,
        ),
        (
            Mods.HIDDEN | Mods.FADEIN,
            3,
            Mods.HIDDEN,
        ),
        (
            Mods.RELAX | Mods.KEY4,
            3,
            Mods.KEY4,
        ),
    ],
)
def test_filter_invalid_combos_removes_incompatible_mods(
    mods: Mods,
    mode_vn: int,
    expected: Mods,
) -> None:
    assert mods.filter_invalid_combos(mode_vn) == expected


def test_filter_invalid_combos_keeps_first_mania_key_mod() -> None:
    assert (Mods.KEY4 | Mods.KEY7).filter_invalid_combos(mode_vn=3) == Mods.KEY4


def test_from_np_filters_user_supplied_mods_for_mode() -> None:
    assert Mods.from_np("+Hidden +FadeIn |4K| |7K|", mode_vn=3) == (
        Mods.HIDDEN | Mods.KEY4
    )
