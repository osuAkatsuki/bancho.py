from __future__ import annotations

from typing import Any
from typing import Generic
from typing import Literal
from typing import TypeVar

from pydantic import BaseModel

from app.api.v2.common import json


T = TypeVar("T")


class Success(BaseModel, Generic[T]):
    status: Literal["success"]
    data: T
    meta: dict[str, Any]


def success(
    content: Any,
    status_code: int = 200,
    headers: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
) -> Any:
    if meta is None:
        meta = {}
    data = {"status": "success", "data": content, "meta": meta}
    return json.ORJSONResponse(data, status_code, headers)


class ErrorResponse(BaseModel, Generic[T]):
    status: Literal["error"]
    error: T
    message: str


def failure(
    # TODO: error code
    message: str,
    status_code: int = 400,
    headers: dict | None = None,
) -> Any:
    data = {"status": "error", "error": message}
    return json.ORJSONResponse(data, status_code, headers)
