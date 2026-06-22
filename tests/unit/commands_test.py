from __future__ import annotations

import pytest

from app.commands import ParsingError
from app.commands import parse__with__command_args
from app.commands import status_to_id
from app.constants.mods import Mods


def test_with_command_arg_parser_accepts_acc_misses_combo_and_mods() -> None:
    parsed = parse__with__command_args(0, ["95.5%", "1m", "429x", "+hddt"])

    assert parsed == {
        "acc": 95.5,
        "mods": Mods.HIDDEN | Mods.DOUBLETIME,
        "combo": 429,
        "nmiss": 1,
    }


@pytest.mark.parametrize(
    ("args", "expected_error"),
    [
        ([], "Invalid syntax: !with <acc/nmiss/combo/mods ...>"),
        (["101%"], "Invalid accuracy."),
        (["bad"], "Unknown argument: bad"),
    ],
)
def test_with_command_arg_parser_rejects_invalid_args(
    args: list[str],
    expected_error: str,
) -> None:
    parsed = parse__with__command_args(0, args)

    assert isinstance(parsed, ParsingError)
    assert str(parsed) == expected_error


@pytest.mark.parametrize(
    ("status", "expected_id"),
    [
        ("unrank", 0),
        ("rank", 2),
        ("love", 5),
    ],
)
def test_status_to_id(status: str, expected_id: int) -> None:
    assert status_to_id(status) == expected_id
