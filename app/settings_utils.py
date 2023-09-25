from __future__ import annotations

import os
import warnings
from datetime import date


def read_bool(value: str) -> bool:
    return value.lower() in ("true", "1", "yes")


def read_list(value: str) -> list[str]:
    return [v.strip() for v in value.split(",")]


def support_deprecated_vars(new_name: str, deprecated_name: str, *, until: date) -> str:
    val = os.getenv(new_name)
    if val is not None:
        return val

    val = os.getenv(deprecated_name)
    if val is not None:
        warnings.warn(
            f"{deprecated_name} has been deprecated and will be supported until {until.isoformat()}. Use  {new_name} instead.",
            DeprecationWarning,
        )
        return val

    raise KeyError(
        f"Neither {new_name} nor {deprecated_name} are set in the environment.",
    )
