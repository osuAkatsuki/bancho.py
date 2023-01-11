from __future__ import annotations

from typing import Any
from typing import Generic
from typing import Literal
from typing import Optional
from typing import TypeVar
from typing import Union

from pydantic.generics import GenericModel

from app.api.v2.common import json


T = TypeVar("T")


class Success(GenericModel, Generic[T]):
    status: Literal["success"]
    data: T
    meta: dict[str, Any]


def success(
    content: Any,
    status_code: int = 200,
    headers: Optional[dict[str, Any]] = None,
    meta: Optional[dict[str, Any]] = None,
) -> Any:
    if meta is None:
        meta = {}
    data = {"status": "success", "data": content, "meta": meta}
    return json.ORJSONResponse(data, status_code, headers)


class ErrorResponse(GenericModel, Generic[T]):
    status: Literal["error"]
    error: T
    message: str


def failure(
    # TODO: error code
    message: str,
    status_code: int = 400,
    headers: Union[dict, None] = None,
) -> Any:
    data = {"status": "error", "error": message}
    return json.ORJSONResponse(data, status_code, headers)
