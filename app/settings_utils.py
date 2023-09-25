from __future__ import annotations


def read_bool(value: str) -> bool:
    return value.lower() in ("true", "1", "yes")


def read_list(value: str) -> list[str]:
    return [v.strip() for v in value.split(",")]
