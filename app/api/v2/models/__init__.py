# isort: dont-add-imports

from pydantic import BaseModel as _pydantic_BaseModel
from pydantic import ConfigDict


class BaseModel(_pydantic_BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, from_attributes=True)
