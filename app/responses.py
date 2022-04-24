from __future__ import annotations

from typing import Mapping

from fastapi import status
from fastapi.responses import ORJSONResponse


def osu_registration_failure(errors: Mapping[str, list[str]]) -> ORJSONResponse:
    """Reformat the errors mapping into a response for the osu! client."""
    errors = {k: ["\n".join(v)] for k, v in errors.items()}

    return ORJSONResponse(
        content={"form_error": {"user": errors}},
        status_code=status.HTTP_400_BAD_REQUEST,
    )
