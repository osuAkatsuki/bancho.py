from __future__ import annotations

from datetime import date
from enum import StrEnum
from functools import cached_property

from app._typing import IPAddress


class OsuStream(StrEnum):
    STABLE = "stable"
    BETA = "beta"
    CUTTINGEDGE = "cuttingedge"
    TOURNEY = "tourney"
    DEV = "dev"


class OsuVersion:
    # b20200201.2cuttingedge
    # date = 2020/02/01
    # revision = 2
    # stream = cuttingedge
    def __init__(
        self,
        date: date,
        revision: int | None,  # TODO: should this be optional?
        stream: OsuStream,
    ) -> None:
        self.date = date
        self.revision = revision
        self.stream = stream


class ClientDetails:
    def __init__(
        self,
        osu_version: OsuVersion,
        osu_path_md5: str,
        adapters_md5: str,
        uninstall_md5: str,
        disk_signature_md5: str,
        adapters: list[str],
        ip: IPAddress,
    ) -> None:
        self.osu_version = osu_version
        self.osu_path_md5 = osu_path_md5
        self.adapters_md5 = adapters_md5
        self.uninstall_md5 = uninstall_md5
        self.disk_signature_md5 = disk_signature_md5

        self.adapters = adapters
        self.ip = ip

    @cached_property
    def client_hash(self) -> str:
        return (
            # NOTE the extra '.' and ':' appended to ends
            f"{self.osu_path_md5}:{'.'.join(self.adapters)}."
            f":{self.adapters_md5}:{self.uninstall_md5}:{self.disk_signature_md5}:"
        )

    # TODO: __str__ to pack like osu! hashes?
