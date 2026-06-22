from __future__ import annotations

from datetime import date

import pytest

from app.api.domains import cho
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
