from __future__ import annotations

from io import BufferedReader
from io import BytesIO
from typing import Dict

from osz2 import KeyType  # type: ignore[import-untyped]
from osz2 import Osz2Package
from slider import Beatmap  # type: ignore[import-untyped]

from app.usecases import maps as maps_usecases


class InternalOsz2(Osz2Package):  # type: ignore[misc]
    """An extension of the osz2 package that implements beatmap parsing with slider"""

    def __init__(  # type: ignore[no-untyped-def]
        self,
        reader: BufferedReader,
        metadata_only=False,
        key_type=KeyType.OSZ2,
    ) -> None:
        super().__init__(reader, metadata_only, key_type)
        self.beatmaps: dict[str, Beatmap] = {}

        if not metadata_only:
            self.populate_beatmaps()

    @classmethod
    def from_bytes(cls, data: bytes, metadata_only=False, key_type=KeyType.OSZ2) -> InternalOsz2:  # type: ignore[no-untyped-def]
        with BytesIO(data) as f:
            return cls(f, metadata_only, key_type)  # type: ignore[arg-type]

    def populate_beatmaps(self) -> None:
        for file in self.beatmap_files:
            beatmap = maps_usecases.parse_beatmap(file.content)

            if beatmap:
                self.beatmaps[file.filename] = beatmap
