from __future__ import annotations

from typing import Any
from typing import Generic
from typing import Literal
from typing import TypeVar
from typing import Union

from pydantic.generics import GenericModel

from app.api.v2.responses import json


T = TypeVar("T")


class ErrorResponse(GenericModel, Generic[T]):
    status: Literal["error"]
    error: T
    message: str


def failure(
    error: str,
    status_code: int = 400,
    headers: Union[dict, None] = None,
) -> json.ORJSONResponse:
    data = {"status": "error", "error": error}
    return json.ORJSONResponse(data, status_code, headers)
