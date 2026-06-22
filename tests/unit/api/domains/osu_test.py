from __future__ import annotations

import io

import pytest
from starlette.datastructures import FormData
from starlette.datastructures import UploadFile

from app.api.domains import osu


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
