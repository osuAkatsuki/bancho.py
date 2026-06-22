from __future__ import annotations

import io
from datetime import date

import pytest
from starlette.datastructures import FormData
from starlette.datastructures import UploadFile

from app.api.domains import cho
from app.api.domains import osu
from app.commands import ParsingError
from app.commands import parse__with__command_args
from app.commands import status_to_id
from app.constants.mods import Mods
from app.objects.player import OsuStream
from app.packets import MultiplayerMatch


def test_parse_login_data_handles_protocol_trailing_newline() -> None:
    login_data = (
        b"cmyui\n"
        b"password-md5\n"
        b"b20230814.2cuttingedge|-5|1|"
        b"osu-path.adapt:1.2.3.:adapters:uninstall:disk:|1\n"
    )

    parsed = cho.parse_login_data(login_data)

    assert parsed == {
        "username": "cmyui",
        "password_md5": b"password-md5",
        "osu_version": "b20230814.2cuttingedge",
        "utc_offset": -5,
        "display_city": True,
        "pm_private": True,
        "osu_path_md5": "osu-path.adapt",
        "adapters_str": "1.2.3.",
        "adapters_md5": "adapters",
        "uninstall_md5": "uninstall",
        "disk_signature_md5": "disk",
    }


@pytest.mark.parametrize(
    ("raw_version", "expected_date", "expected_revision", "expected_stream"),
    [
        ("b20230814", date(2023, 8, 14), None, OsuStream.STABLE),
        ("b20230814.2cuttingedge", date(2023, 8, 14), 2, OsuStream.CUTTINGEDGE),
        ("b20230814beta", date(2023, 8, 14), None, OsuStream.BETA),
    ],
)
def test_parse_osu_version_string(
    raw_version: str,
    expected_date: date,
    expected_revision: int | None,
    expected_stream: OsuStream,
) -> None:
    parsed = cho.parse_osu_version_string(raw_version)

    assert parsed is not None
    assert parsed.date == expected_date
    assert parsed.revision == expected_revision
    assert parsed.stream is expected_stream


def test_parse_osu_version_string_rejects_invalid_versions() -> None:
    assert cho.parse_osu_version_string("definitely-not-osu") is None


def test_parse_adapters_string() -> None:
    adapters, running_under_wine = cho.parse_adapters_string("1.2.3.")

    assert adapters == ["1", "2", "3"]
    assert running_under_wine is False


def test_parse_adapters_string_detects_wine() -> None:
    _, running_under_wine = cho.parse_adapters_string("runningunderwine")

    assert running_under_wine is True


def test_validate_match_data_accepts_expected_host_and_reasonable_name() -> None:
    match_data = MultiplayerMatch()
    match_data.host_id = 32
    match_data.name = "friendly lobby"

    assert cho.validate_match_data(match_data, expected_host_id=32) is True


@pytest.mark.parametrize(
    ("host_id", "name", "expected_host_id"),
    [
        (99, "friendly lobby", 32),
        (32, "x" * (cho.MAX_MATCH_NAME_LENGTH + 1), 32),
    ],
)
def test_validate_match_data_rejects_untrusted_fields(
    host_id: int,
    name: str,
    expected_host_id: int,
) -> None:
    match_data = MultiplayerMatch()
    match_data.host_id = host_id
    match_data.name = name

    assert cho.validate_match_data(match_data, expected_host_id) is False


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


def test_osu_chart_entry_formats_optional_before_and_after_values() -> None:
    assert osu.chart_entry("rankedScore", None, 123.45) == (
        "rankedScoreBefore:|rankedScoreAfter:123.45"
    )


def test_osu_achievement_string_uses_client_delimiters() -> None:
    assert (
        osu.format_achievement_string(
            "osu-combo-500",
            "500 Combo",
            "Achieve a 500 combo.",
        )
        == "osu-combo-500+500 Combo+Achieve a 500 combo."
    )


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
