from __future__ import annotations

import os
from datetime import date

from app.logging import Ansi
from app.logging import log


def read_bool(value: str) -> bool:
    return value.lower() in ("true", "1", "yes")


def read_list(value: str) -> list[str]:
    return [v.strip() for v in value.split(",")]


def support_deprecated_vars(
    new_name: str,
    deprecated_name: str,
    *,
    until: date,
    allow_empty_string: bool = False,
) -> str:
    val1 = os.getenv(new_name)
    if val1:
        return val1

    val2 = os.getenv(deprecated_name)
    if val2:
        log(
            f'The "{deprecated_name}" config option has been deprecated and will be supported until {until.isoformat()}. Use {new_name} instead.',
            Ansi.LYELLOW,
        )
        return val2

    if allow_empty_string:
        if val1 is not None:
            return val1
        if val2 is not None:
            return val2

    raise KeyError(f"{new_name} is not set in the environment")
