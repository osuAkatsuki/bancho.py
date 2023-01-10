from __future__ import annotations

from typing import Any
from typing import Generic
from typing import Literal
from typing import TypeVar
from typing import Union

from pydantic.generics import GenericModel

from app.api.v2.responses import json


T = TypeVar("T")


class Success(GenericModel, Generic[T]):
    status: Literal["success"]
    data: T


def success(
    content: Any,
    status_code: int = 200,
    headers: Union[dict, None] = None,
) -> json.ORJSONResponse:
    data = {"status": "success", "data": content}
    return json.ORJSONResponse(data, status_code, headers)
