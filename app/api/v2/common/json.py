from __future__ import annotations

from typing import Any
from typing import cast

import orjson
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing_extensions import override


def _default_processor(data: Any) -> Any:
    if isinstance(data, BaseModel):
        return _default_processor(data.dict())
    elif isinstance(data, dict):
        return {
            str(k): _default_processor(v)
            for k, v in cast(dict[object, object], data).items()
        }
    elif isinstance(data, list):
        return [_default_processor(v) for v in cast(list[object], data)]
    else:
        return data


def dumps(data: Any) -> bytes:
    return orjson.dumps(data, default=_default_processor)


class ORJSONResponse(JSONResponse):
    media_type = "application/json"

    @override
    def render(self, content: Any) -> bytes:
        return dumps(content)
