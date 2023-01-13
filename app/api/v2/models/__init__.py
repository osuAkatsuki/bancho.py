from __future__ import annotations

from typing import Any
from typing import Mapping
from typing import TypeVar

from pydantic import BaseModel as _pydantic_BaseModel


T = TypeVar("T", bound=type["BaseModel"])


class BaseModel(_pydantic_BaseModel):
    class Config:
        anystr_strip_whitespace = True

    @classmethod
    def from_mapping(cls: T, mapping: Mapping[str, Any]) -> T:
        return cls(**{k: mapping[k] for k in cls.__fields__})
