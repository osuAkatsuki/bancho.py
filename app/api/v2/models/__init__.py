from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from typing import TypeVar

from pydantic import BaseModel as _pydantic_BaseModel
from pydantic import ConfigDict


T = TypeVar("T", bound="BaseModel")


class BaseModel(_pydantic_BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    @classmethod
    def from_mapping(cls: type[T], mapping: Mapping[str, Any]) -> T:
        return cls(**{k: mapping[k] for k in cls.model_fields})
